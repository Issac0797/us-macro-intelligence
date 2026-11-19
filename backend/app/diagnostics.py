"""Safe request budgets and bounded diagnostic records. Never log query strings/bodies."""
from contextvars import ContextVar
from dataclasses import dataclass, field
from contextlib import contextmanager
from collections import deque
import asyncio
import json
import logging
import re
import threading
import time
from uuid import uuid4
from fastapi import HTTPException
from starlette.responses import JSONResponse


@dataclass
class Budget:
    request_id: str
    deadline: float
    cancelled: threading.Event = field(default_factory=threading.Event)
    database_ms: float = 0
    calculation_ms: float = 0
    serialization_ms: float = 0
    cache: str = 'none'
    reason: str | None = None
    shared_work: object = None


active = ContextVar('request_budget', default=None)
records = deque(maxlen=200)
log = logging.getLogger('macro.requests')
log.setLevel(logging.INFO)
if not log.handlers:
    handler=logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(handler)
log.propagate=False


def checkpoint():
    b = active.get()
    if b and ((b.cancelled.is_set() and not (b.shared_work and b.shared_work())) or time.monotonic() > b.deadline):
        b.reason = 'client_disconnected' if b.cancelled.is_set() else 'request_budget'
        raise HTTPException(504, 'Research request exceeded its processing budget; narrow the range and retry')


def cache_event(value):
    b = active.get()
    if b and b.cache == 'none':
        b.cache = value


@contextmanager
def phase(name):
    checkpoint()
    start = time.perf_counter()
    initial_db=active.get().database_ms if active.get() else 0
    try:
        yield
    finally:
        b = active.get()
        if b:
            elapsed=(time.perf_counter()-start)*1000
            if name=='calculation':elapsed=max(0,elapsed-(b.database_ms-initial_db))
            setattr(b, name + '_ms', getattr(b, name + '_ms') + elapsed)


class TimedJSONResponse(JSONResponse):
    def render(self, content):
        with phase('serialization'):
            return super().render(content)


class DiagnosticsMiddleware:
    def __init__(self, app):
        self.app = app
        self.slots = asyncio.Semaphore(16)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api/'):
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        supplied = headers.get(b'x-request-id', b'').decode('ascii', 'ignore')
        rid = supplied if re.fullmatch(r'[a-zA-Z0-9-]{8,64}', supplied) else str(uuid4())
        b = Budget(rid, time.monotonic() + 20)
        token = active.set(b)
        started = time.perf_counter()
        status = 500
        acquired = False
        watcher = None
        try:
            try:
                await asyncio.wait_for(self.slots.acquire(), .5)
                acquired = True
            except asyncio.TimeoutError:
                b.reason = 'concurrency_budget'
                status=429
                return await JSONResponse({'detail': 'Data service is busy; retry shortly'}, status_code=429,
                                          headers={'Retry-After': '1', 'X-Request-ID': rid})(scope, receive, send)
            # Buffer only the bounded API request body, then independently observe disconnects.
            body = b''
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    b.cancelled.set()
                    return
                body += message.get('body', b'')
                if len(body) > 131072:
                    return await JSONResponse({'detail': 'Request exceeds 128 KiB'}, status_code=413)(scope, receive, send)
                if not message.get('more_body'):
                    break
            delivered = False
            disconnected = asyncio.Event()
            async def watch():
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        b.cancelled.set()
                        disconnected.set()
                        return
            watcher = asyncio.create_task(watch())
            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': body, 'more_body': False}
                await disconnected.wait()
                return {'type': 'http.disconnect'}
            async def traced(message):
                nonlocal status
                if message['type'] == 'http.response.start':
                    status = message['status']
                    message['headers'] = list(message.get('headers', [])) + [
                        (b'x-request-id', rid.encode()), (b'x-cache', b.cache.encode()),
                        (b'server-timing', f'db;dur={b.database_ms:.2f}, calc;dur={b.calculation_ms:.2f}, json;dur={b.serialization_ms:.2f}'.encode())]
                await send(message)
            await self.app(scope, replay, traced)
        finally:
            if watcher:
                watcher.cancel()
            if acquired:
                self.slots.release()
            entry = dict(request_id=rid, endpoint=scope['path'], http_status=status,
                         total_ms=round((time.perf_counter()-started)*1000, 2),
                         database_ms=round(b.database_ms, 2), calculation_ms=round(b.calculation_ms, 2),
                         serialization_ms=round(b.serialization_ms, 2), cache=b.cache,
                         timeout_reason=b.reason, retry_count=min(8,int(headers.get(b'x-retry-count',b'0'))) if headers.get(b'x-retry-count',b'0').isdigit() else 0)
            records.append(entry)
            log.info(json.dumps(entry))
            active.reset(token)

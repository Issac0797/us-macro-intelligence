"""Process-local bounded TTL/LRU + single-flight. Errors are never cached."""
from collections import OrderedDict
from concurrent.futures import Future, TimeoutError
from copy import deepcopy
from threading import RLock
import pickle
import time


class BoundedCache:
    def __init__(self, capacity=32 * 1024 * 1024, entries=128):
        self.capacity, self.entries = capacity, entries
        self.values, self.pending = OrderedDict(), {}
        self.waiters = {}
        self.lock = RLock()
        self.bytes = self.hits = self.misses = self.shared = 0

    def clear(self):
        with self.lock:
            self.values.clear()
            self.bytes = 0

    def get(self, key, compute, ttl=30, copy=True):
        from app.diagnostics import checkpoint, cache_event
        checkpoint()
        now = time.monotonic()
        with self.lock:
            for old in list(self.values):
                if self.values[old][0] <= now:
                    self.bytes -= self.values.pop(old)[2]
            if key in self.values:
                self.hits += 1
                self.values.move_to_end(key)
                value = self.values[key][1]
                cache_event('hit')
                return deepcopy(value) if copy else value
            if key in self.pending:
                future, owner = self.pending[key], False
                self.shared += 1
                self.waiters[key]=self.waiters.get(key,0)+1
                cache_event('shared')
            else:
                future, owner = Future(), True
                self.pending[key] = future
                self.misses += 1
                cache_event('miss')
        if not owner:
            try:
                while True:
                    checkpoint()
                    try:
                        value = future.result(timeout=.1)
                        return deepcopy(value) if copy else value
                    except TimeoutError:
                        if future.done():raise
            finally:
                with self.lock:self.waiters[key]=max(0,self.waiters.get(key,1)-1)
        from app.diagnostics import active
        budget=active.get();old_shared=budget.shared_work if budget else None
        if budget:budget.shared_work=lambda:self.waiters.get(key,0)>0
        try:
            value = compute()
            # Conservative charge for Python graph overhead; oversized entries are not retained.
            size = len(pickle.dumps(value, protocol=5)) * 4
            with self.lock:
                if size <= self.capacity:
                    while self.values and (self.bytes + size > self.capacity or len(self.values) >= self.entries):
                        self.bytes -= self.values.popitem(last=False)[1][2]
                    self.values[key] = (time.monotonic() + ttl, value, size)
                    self.bytes += size
                future.set_result(value)
            return deepcopy(value) if copy else value
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            if budget:budget.shared_work=old_shared
            with self.lock:
                self.pending.pop(key, None)
                if self.waiters.get(key,0)==0:self.waiters.pop(key,None)

    def stats(self):
        with self.lock:
            return dict(entries=len(self.values), charged_bytes=self.bytes, capacity=self.capacity,
                        pending=len(self.pending), hits=self.hits, misses=self.misses, shared=self.shared)


results = BoundedCache()
native = BoundedCache(capacity=96 * 1024 * 1024, entries=32)


def dataset_version(db):
    """Commit-visible DB watermark; separate processes see syncs without a message broker."""
    from sqlalchemy import select, func
    from app.models import Observation, Series
    from app.vintage_models import VintageArchive
    from app.fed.models import Document
    if db.new or db.dirty or db.deleted:db.flush()
    if db.info.get('watermark_transaction') is db.get_transaction() and 'watermark' in db.info:
        return db.info['watermark']
    row = db.execute(select(
        select(func.max(Observation.id)).scalar_subquery(),
        select(func.max(Series.last_synced_at)).scalar_subquery(),
        select(func.max(VintageArchive.retrieved_at)).scalar_subquery(),
        select(func.max(Document.parsed_at)).scalar_subquery())).one()
    version=(str(db.bind.url), id(db.bind), *map(str, row))
    db.info['watermark_transaction']=db.get_transaction();db.info['watermark']=version
    return version

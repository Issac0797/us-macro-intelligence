"""Isolated test-server wrapper. NOT imported by production; no control HTTP endpoint."""
import asyncio
import json
from pathlib import Path
from starlette.responses import JSONResponse, Response
from app.main import app as real_app
from app.bounded_cache import results, native

CONTROL = Path(__file__).resolve().parents[2] / '.local/iteration8-phase-b/control.json'


async def app(scope, receive, send):
    if scope['type'] == 'http' and CONTROL.exists():
        control = json.loads(CONTROL.read_text(encoding='utf-8'))
        if control.pop('clear_cache', False):
            results.clear(); native.clear()
            CONTROL.write_text(json.dumps(control), encoding='utf-8')
        if scope['path'] == control.get('path') and control.get('remaining', 0) > 0:
            control['remaining'] -= 1
            CONTROL.write_text(json.dumps(control), encoding='utf-8')
            await asyncio.sleep(control.get('delay', 0))
            response = Response('bad-json', status_code=200, media_type='application/json') if control.get('invalid_json') else JSONResponse(
                {'detail': 'CONTROLLED_TRANSIENT_503'}, status_code=control.get('status', 503))
            return await response(scope, receive, send)
    return await real_app(scope, receive, send)

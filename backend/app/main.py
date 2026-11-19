import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import Request, Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Observation, Series, SyncTask, utcnow
from app.schemas import Card, ObservationResponse, Overview, SeriesOut
from app.sync import latest_observations
from app.transforms import Transform, allowed_transforms, calculate, output_units


@asynccontextmanager
async def lifespan(app):
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from app.config import get_settings
    import subprocess,sys,os
    worker=None
    if get_settings().monitor_enabled:
        worker=subprocess.Popen([sys.executable,'-m','app.monitor','--bootstrap'],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    try:
        yield
    finally:
        if worker:
            worker.terminate()
            try: worker.wait(timeout=5)
            except subprocess.TimeoutExpired: worker.kill();worker.wait()


from app.diagnostics import DiagnosticsMiddleware, TimedJSONResponse, phase

app = FastAPI(default_response_class=TimedJSONResponse,title="US Macro Intelligence", version="0.1.0", lifespan=lifespan,
    description="Native FRED observations, local revision history and validated macroeconomic transformations.")
app.add_middleware(DiagnosticsMiddleware)
from app.calendar_api import router as calendar_router
app.include_router(calendar_router)
from app.vintage_api import router as vintage_router
app.include_router(vintage_router)
from app.workspace_api import router as workspace_router
app.include_router(workspace_router)
from app.analytics.api import router as analytics_router
app.include_router(analytics_router)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def invalid_request(request,exc):
    if request.url.path.startswith(('/api/v1/workspace','/api/v1/yield-curve','/api/v1/analytics','/api/v1/business-cycle','/api/v1/recession-indicators')):
        messages=['.'.join(str(p) for p in e['loc'])+': '+e['msg'] for e in exc.errors()[:8]]
        message='Invalid research request: '+'; '.join(messages)
        return JSONResponse(status_code=422,content={'detail':message,'error':{'code':'INVALID_INPUT','message':message}})
    return JSONResponse(status_code=422,content={'detail':'Invalid query or path parameters','error':{'code':'INVALID_INPUT','message':'Invalid query or path parameters'}})

@app.exception_handler(HTTPException)
async def api_error(request,exc):
    return JSONResponse(status_code=exc.status_code,content={'detail':exc.detail,'error':{'code':f'HTTP_{exc.status_code}','message':exc.detail}})

@app.exception_handler(SQLAlchemyError)
async def storage_error(request,exc):
    from app.diagnostics import active
    b=active.get()
    logging.getLogger('macro.requests').error('storage_failure request_id=%s type=%s',b.request_id if b else '',type(exc).__name__)
    if getattr(getattr(exc,'orig',None),'sqlstate',None)=='57014':
        if b:b.reason='database_statement_timeout'
        return JSONResponse(status_code=504,content={'detail':'Database query budget exceeded','error':{'code':'QUERY_TIMEOUT','message':'Narrow the range and retry'}})
    return JSONResponse(status_code=503,content={'detail':'Data storage unavailable','error':{'code':'STORAGE_UNAVAILABLE','message':'Data storage unavailable'}})
DB = Annotated[Session, Depends(get_db)]
PREFIX = "/api/v1"


def describe(series):
    return SeriesOut.model_validate(series).model_copy(update={"available_transforms": allowed_transforms(series)})


def get_series(db, series_id):
    series = db.get(Series, series_id.upper())
    if not series:
        raise HTTPException(404, "Unknown series")
    return series


@app.get(PREFIX + "/health", tags=["system"])
def health(db: DB):
    try:
        db.execute(text("SELECT 1"))
        count = db.scalar(select(func.count()).select_from(Observation))
        return {"status": "ok", "database": "connected", "observation_versions": count,
                "data_status": "ready" if count else "empty"}
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable or migrations not applied") from None


@app.get(PREFIX + "/series", response_model=list[SeriesOut], tags=["series"])
def list_series(db: DB, category: str | None = None):
    query = select(Series).order_by(Series.id)
    if category:
        query = query.where(Series.category == category)
    return [describe(s) for s in db.scalars(query)]


@app.get(PREFIX + "/series/{series_id}", response_model=SeriesOut, tags=["series"])
def series_detail(series_id: str, db: DB):
    return describe(get_series(db, series_id))


@app.get(PREFIX + "/series/{series_id}/observations", response_model=ObservationResponse, tags=["observations"])
def observations(series_id: str, db: DB, transform: Transform = Transform.RAW,
                 start: date | None = None, end: date | None = None,
                 window: int = Query(3, ge=2, le=365), limit: int = Query(5000, ge=1, le=100000),
                 offset: int = Query(0, ge=0), as_of: datetime | None = None):
    if start and end and start > end:
        raise HTTPException(422, "start must not be later than end")
    if as_of and (as_of.tzinfo is None or as_of.utcoffset() is None):
        raise HTTPException(422, "as_of requires a timezone, e.g. 2026-01-01T00:00:00Z")
    series = get_series(db, series_id)
    from app.read_queries import observation_rows, warmup_count
    rows = db.execute(observation_rows(db, series.id, start=start, end=end, as_of=as_of, warmup=warmup_count(series, transform, window))).all()
    try:
        points = calculate(series, rows, transform, window)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    # Compute against full history first so the first displayed point has warm-up data.
    points = [p for p in points if (not start or p["date"] >= start) and (not end or p["date"] <= end)]
    from app.availability import availability
    native = [dict(value=r.value) for r in rows]
    has_history = bool(rows) or db.scalar(select(Observation.id).where(Observation.series_id == series.id).limit(1)) is not None
    state = availability(native, points, points, has_history=has_history)
    if not points and rows:
        state['status'] = 'NO_OBSERVATIONS_IN_RANGE'
    return dict(series=describe(series), transform=transform, units=output_units(series, transform),
                window=window if transform == Transform.MOVING_AVERAGE else None,
                count=len(points), offset=offset, limit=limit, observations=points[offset:offset + limit], availability=state)


@app.get(PREFIX + "/overview", response_model=Overview, tags=["overview"])
def overview(db: DB, category: str | None = None):
    from app.overview_service import build_overview
    from app.bounded_cache import results, dataset_version
    version=dataset_version(db)
    def compute():
        with phase('calculation'):payload=build_overview(db, category)
        with phase('serialization'):return payload.model_dump_json().encode('utf-8')
    from fastapi.responses import Response
    content=results.get(('overview',category,date.today(),version),compute,ttl=15,copy=False)
    return Response(content=content,media_type='application/json')

from app.fed.api import router as fed_router
app.include_router(fed_router)


@app.get(PREFIX+'/data-version',tags=['system'])
def data_version(db:DB):
    from app.bounded_cache import dataset_version
    from app.workspace_engine import digest
    return {'version':digest(dataset_version(db)[2:]),'checked_at':utcnow()}

@app.get(PREFIX+'/diagnostics',tags=['system'])
def diagnostics(request:Request,db:DB):
    from app.config import get_settings
    import ipaddress
    host=request.client.host if request.client else ''
    try:local=ipaddress.ip_address(host).is_loopback
    except ValueError:local=False
    if not get_settings().diagnostics_enabled or not local:raise HTTPException(404,'Not found')
    from app.diagnostics import records
    from app.bounded_cache import results,native
    from app.sync_schedule import sync_states
    return {'recent_requests':list(records),'cache':{'results':results.stats(),'native':native.stats()},'series_sync':sync_states(db)}

from app.observation_details import router as observation_details_router
app.include_router(observation_details_router)

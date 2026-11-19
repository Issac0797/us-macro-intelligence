from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from threading import Event
import time
import pytest
from sqlalchemy import select, event
from fastapi import HTTPException
from app.bounded_cache import BoundedCache, dataset_version
from app.diagnostics import Budget, active, checkpoint
from app.models import Series, Observation
from app.overview_service import build_overview
from app.read_queries import observation_rows, warmup_count
from app.sync import latest_observations, sync_series
from app.transforms import Transform, calculate
from app.sync_schedule import sync_states
from app.providers import ProviderError, Datum


def populate(db,sid='CPIAUCSL',count=180):
    series=db.get(Series,sid)
    for i in range(count):
        d=date(2000+i//12,i%12+1,1)
        v=None if i%23==0 else Decimal(100+i)
        db.add(Observation(series_id=sid,observation_date=d,value=v,raw_value=str(v) if v is not None else '.',
            units=series.units,source='fred_api',source_url=series.source_url,version=str(i),collected_at=datetime(2024,1,1,tzinfo=timezone.utc)))
    db.commit()


@pytest.mark.parametrize('op',list(Transform))
def test_bounded_warmup_matches_full_history(db,op):
    populate(db)
    s=db.get(Series,'CPIAUCSL');start=date(2010,1,1);end=date(2014,1,1)
    full=calculate(s,list(db.scalars(latest_observations(db,s.id))),op,12)
    bounded=calculate(s,db.execute(observation_rows(db,s.id,start=start,end=end,warmup=warmup_count(s,op,12))).all(),op,12)
    assert [p for p in full if start<=p['date']<=end]==[p for p in bounded if start<=p['date']<=end]
    assert not any(isinstance(v,Observation) for v in db.identity_map.values())


def test_overview_long_missing_tail_still_finds_last_valid(db):
    populate(db,count=180)
    for row in db.scalars(select(Observation).where(Observation.observation_date>=date(2005,1,1))):
        row.value=None;row.raw_value='.'
    db.commit()
    series=db.get(Series,'CPIAUCSL')
    expected=calculate(series,list(db.scalars(latest_observations(db,series.id))),Transform(series.default_transform))
    valid=[p for p in expected if p['value'] is not None]
    card=next(c for c in build_overview(db).cards if c.series.id==series.id)
    assert card.value==valid[-1]['value'] and card.previous_value==valid[-2]['value']
    assert [p.model_dump() for p in card.history]==expected[-36:]


def test_local_revision_cutoff_is_applied_before_rank(db):
    populate(db,count=2)
    first=db.scalar(select(Observation).where(Observation.observation_date==date(2000,2,1)))
    db.add(Observation(series_id=first.series_id,observation_date=first.observation_date,value=999,raw_value='999',units=first.units,source='fred_api',source_url=first.source_url,version='future',collected_at=datetime(2025,1,1,tzinfo=timezone.utc)))
    db.commit()
    old=db.execute(observation_rows(db,first.series_id,as_of=datetime(2024,6,1,tzinfo=timezone.utc),tail=1)).one()
    assert old.value==101


def test_cache_single_flight_capacity_copy_and_failures():
    cache=BoundedCache(capacity=4096,entries=2);gate=Event();started=Event();calls=[]
    def compute():calls.append(1);started.set();assert gate.wait(3);return {'v':[1]}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(cache.get,'same',compute) for _ in range(8)]
        assert started.wait(3);gate.set();answers=[f.result() for f in futures]
    assert len(calls)==1 and all(a=={'v':[1]} for a in answers)
    answers[0]['v'].append(2);assert cache.get('same',compute)=={'v':[1]}
    for n in range(8):cache.get(n,lambda:n)
    assert cache.stats()['entries']<=2 and cache.bytes<=4096
    with pytest.raises(ValueError):cache.get('bad',lambda:(_ for _ in ()).throw(ValueError('temporary')))
    assert cache.get('bad',lambda:42)==42


def test_cache_ttl_and_vintage_keys():
    c=BoundedCache();assert c.get(('vintage','2023-01-01'),lambda:1,ttl=0)==1
    assert c.get(('vintage','2023-01-01'),lambda:2)==2
    assert c.get(('vintage','2023-02-01'),lambda:3)==3
    assert c.get(('latest',None),lambda:4)==4


def test_generation_changes_only_after_committed_sync(db):
    before=dataset_version(db)
    class P:
        name='fred_api'
        def metadata(self,sid):return {}
        def observations(self,*a):return [Datum(date(2025,1,1),Decimal(4),'4')]
    sync_series(db,P(),'DFF');after=dataset_version(db);assert before!=after
    assert db.scalar(select(Observation.value).where(Observation.series_id=='DFF'))==4


def test_sync_state_no_new_blocked_failure_and_compensation(db):
    class P:
        name='fred_api'
        def metadata(self,sid):return {}
        def observations(self,*a):return [Datum(date(2025,1,1),Decimal(4),'4')]
    p=P();sync_series(db,p,'DFF');sync_series(db,p,'DFF')
    state=next(s for s in sync_states(db) if s['series_id']=='DFF')
    assert state['state']=='NO_NEW_OBSERVATION' and state['last_successful_sync'] and state['next_scheduled_attempt']>state['last_attempt']
    class Broken(P):
        def observations(self,*a):raise ProviderError('credential-bearing details',403)
    with pytest.raises(ProviderError):sync_series(db,Broken(),'DGS10')
    blocked=next(s for s in sync_states(db) if s['series_id']=='DGS10')
    assert blocked['state']=='SOURCE_BLOCKED' and 'credential' not in blocked['last_error']
    sync_series(db,p,'DGS10');assert next(s for s in sync_states(db) if s['series_id']=='DGS10')['state']=='SUCCESS'


def test_budget_expiration_and_disconnect():
    b=Budget('test-request',time.monotonic()-1);token=active.set(b)
    try:
        with pytest.raises(HTTPException) as e:checkpoint()
        assert e.value.status_code==504 and b.reason=='request_budget'
        b.deadline=time.monotonic()+10;b.cancelled.set()
        with pytest.raises(HTTPException):checkpoint()
        assert b.reason=='client_disconnected'
    finally:active.reset(token)


def test_diagnostics_disabled_and_request_correlation(client):
    r=client.get('/api/v1/overview',headers={'X-Request-ID':'reliability-test-123'})
    assert r.status_code==200 and r.headers['x-request-id']=='reliability-test-123'
    assert 'db;dur=' in r.headers['server-timing'] and r.headers['x-cache'] in ['hit','miss','shared']
    assert client.get('/api/v1/diagnostics').status_code==404
    assert client.get('/api/v1/data-version').json()['version']


def test_series_scheduler_failure_does_not_block_other_series(db,monkeypatch):
    from contextlib import contextmanager
    from app.sync_schedule import reconcile_due
    @contextmanager
    def sessions():
        yield db
    monkeypatch.setattr('app.db.SessionLocal',sessions)
    class P:
        name='fred_api'
        def metadata(self,sid):return {}
        def observations(self,sid,*args):
            if sid=='CPIAUCSL':raise ProviderError('temporary')
            return [Datum(date(2025,1,1),Decimal(4),'4')]
    results=reconcile_due(P())
    assert len(results)==10
    assert next(r for r in results if r[0]=='CPIAUCSL')[1]=='ProviderError'
    assert next(r for r in results if r[0]=='DFF')[1]=='succeeded'


def test_cache_owner_timeout_is_not_an_infinite_wait():
    cache=BoundedCache();gate=Event();started=Event()
    def fail():started.set();gate.wait(2);raise TimeoutError('owner timed out')
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner=pool.submit(cache.get,'key',fail);assert started.wait(2)
        waiter=pool.submit(cache.get,'key',lambda:42)
        time.sleep(.02);gate.set()
        for f in [owner,waiter]:
            with pytest.raises(TimeoutError):f.result(timeout=2)


def test_latest_cycle_evaluation_dates_reuse_one_native_dataset(db,monkeypatch):
    from app import workspace_engine as w
    from app.bounded_cache import native
    native.clear();calls=[]
    monkeypatch.setattr(w,'_native_history',lambda *a:(calls.append(a[-1]) or ('spec',[],{})))
    a=w.native_history(db,'DFF','latest',date(2026,10,31))
    b=w.native_history(db,'DFF','latest',date(2026,11,16))
    assert a==b and calls==[None]
    w.native_history(db,'DFF','vintage',date(2023,1,1))
    w.native_history(db,'DFF','vintage',date(2023,2,1))
    assert calls==[None,date(2023,1,1),date(2023,2,1)]


def test_cancelled_cache_owner_preserves_remaining_consumer():
    c=BoundedCache();start=Event();finish=Event();budget=Budget('owner',time.monotonic()+3)
    def owner():
        token=active.set(budget)
        def compute():start.set();finish.wait(2);checkpoint();return 9
        try:return c.get('key',compute)
        finally:active.reset(token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(owner);assert start.wait(2)
        b=pool.submit(c.get,'key',lambda:42)
        until=time.monotonic()+2
        while not c.waiters.get('key') and time.monotonic()<until:time.sleep(.001)
        assert c.waiters['key']==1
        budget.cancelled.set();finish.set()
        assert b.result(timeout=2)==a.result(timeout=2)==9


def test_postgres_statement_timeout_releases_connection():
    import os
    if not os.getenv('TEST_DATABASE_URL'):pytest.skip('PostgreSQL integration URL not configured')
    from app.db import make_engine
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    engine=make_engine(os.environ['TEST_DATABASE_URL']);token=None
    try:
        with engine.connect() as c:
            # Time the SQL execution, excluding cold connection/driver initialization.
            budget=Budget('sql-budget',time.monotonic()+.15);token=active.set(budget)
            with pytest.raises(DBAPIError) as exc:c.execute(text('SELECT pg_sleep(2)'))
            assert exc.value.orig.sqlstate=='57014'
            c.rollback()
    finally:
        if token is not None:active.reset(token)
    with engine.connect() as c:assert c.scalar(text('SELECT 1'))==1
    engine.dispose()


def test_temporary_database_unavailable_recovers_without_touching_database(client,monkeypatch):
    from app.main import app
    from app.db import get_db
    from sqlalchemy.exc import OperationalError
    original=app.dependency_overrides[get_db]
    def unavailable():
        raise OperationalError('controlled test failure',{},Exception('database temporarily unavailable'))
        yield
    app.dependency_overrides[get_db]=unavailable
    try:
        response=client.get('/api/v1/workspace/observation-details?series_id=CPIAUCSL&observation_date=2020-01-01')
        assert response.status_code==503 and response.json()['error']
        assert 'controlled test failure' not in response.text
    finally:
        app.dependency_overrides[get_db]=original
    assert client.get('/api/v1/workspace/observation-details?series_id=CPIAUCSL&observation_date=2020-01-01').status_code==200

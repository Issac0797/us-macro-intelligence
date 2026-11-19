from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from types import SimpleNamespace
from pathlib import Path
import hashlib
import pytest
from sqlalchemy import select,func
from app.calendar_providers import ScheduledRelease,parse_ics,parse_bea,parse_census,parse_fomc,parse_g17,ny_time
from app.release_service import refresh_calendar,run_job,reference_date,aware,polling_delay
from app.release_models import ReleaseEvent,ReleaseEventSeries,ReleaseObservation,ObservationRevision,ReleaseMonitorJob,ScheduleChange,CalendarProviderState
from app.models import Observation,Series
from app.sync import sync_series
from app.config import Settings
from app.providers import Datum,ProviderError

UTC=timezone.utc
NOW=datetime.now(UTC)
CURRENT=date(NOW.year,NOW.month,1)
NEW_PERIOD=(CURRENT-timedelta(days=1)).replace(day=1)
BASE_PERIOD=(NEW_PERIOD-timedelta(days=1)).replace(day=1)

class CalendarFixture:
    name='bea';url='https://www.bea.gov/news/schedule'
    def __init__(self):
        self.rows=[ScheduledRelease('official-id','Personal Income and Outlays',(NOW+timedelta(days=1)).date(),NOW+timedelta(days=1),('PCEPI','PCEPILFE'),'inflation',NEW_PERIOD.strftime('%B %Y'),self.url)]
    def fetch(self): return self.rows

class DataFixture:
    name='fred_api'
    def __init__(self): self.rows=[Datum(BASE_PERIOD,Decimal('100'),'100')]
    def metadata(self,sid):return {'source_updated_at':datetime.now(UTC)}
    def observations(self,*args):return self.rows

def setup_event(db):
    provider=DataFixture()
    for sid in ('PCEPI','PCEPILFE'):sync_series(db,provider,sid)
    cal=CalendarFixture();refresh_calendar(db,cal,NOW)
    return db.scalar(select(ReleaseEvent)),provider,cal

@pytest.mark.parametrize('day,hour',[(date(2026,1,15),13),(date(2026,7,15),12)])
def test_dst_utc_conversion(day,hour):
    assert ny_time(day,'8:30 AM').hour==hour
    assert ny_time(day,'8:30 AM').tzinfo==UTC

def test_official_ics_multi_indicator():
    body='BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:official-cpi\r\nSUMMARY:Consumer Price Index\r\nDTSTART;TZID=America/New_York:20261110T083000\r\nEND:VEVENT\r\nEND:VCALENDAR'
    rows=parse_ics(body,'https://www.bls.gov/schedule/news_release/bls.ics')
    assert rows[0].at==datetime(2026,11,10,13,30,tzinfo=UTC)
    assert rows[0].series==('CPIAUCSL','CPILFESL')

def test_bea_html():
    body='<table id="release-schedule-table"><thead><tr><th>Year 2026</th></tr></thead><tbody><tr><td><div class="release-date">November 25</div><small>8:30 AM</small></td><td class="release-title">Personal Income and Outlays, October 2026</td></tr></tbody></table>'
    e=parse_bea(body,'https://www.bea.gov/news/schedule')[0]
    assert e.period.strip()=='October 2026' and e.at.hour==13 and len(e.series)==2

def test_census_html():
    body='<table id="calendar"><tr><td><a>Advance Monthly Sales for Retail and Food Services</a></td><td>January 15, 2027</td><td>8:30 AM</td><td>December 2026</td></tr></table>'
    e=parse_census(body,'https://www.census.gov/')[0]
    assert e.series==('RSAFS',) and e.period=='December 2026'

def test_fomc_does_not_invent_statement_times():
    body='<div class="panel"><div class="panel-heading">2026 FOMC Meetings</div><div class="fomc-meeting"><div class="fomc-meeting__month">Apr/May</div><div class="fomc-meeting__date">30-1</div></div></div>'
    e=parse_fomc(body,'https://www.federalreserve.gov/')[0]
    assert e.at is None and e.day==date(2026,4,30) and not e.released

def test_g17_uses_official_times_only():
    body='The G.17 release will be issued on the following dates. The monthly releases are issued at 9:15 a.m. The annual revision is issued at noon. 2026: November 17, November 24 (annual revision), and December 16. Historical Release Dates'
    rows=parse_g17(body,'https://www.federalreserve.gov/releases/g17/')
    assert len(rows)==3 and rows[0].at.hour==14 and rows[1].at.hour==17

@pytest.mark.parametrize('parser',[parse_ics,parse_bea,parse_census,parse_fomc,parse_g17])
def test_structure_change_fails_closed(parser):
    with pytest.raises((ProviderError,ValueError)):parser('<html>Structure changed</html>','https://agency.gov/')

def test_schedule_dedup_change_and_multi_link(db):
    _,_,cal=setup_event(db);refresh_calendar(db,cal,NOW)
    assert db.scalar(select(func.count()).select_from(ReleaseEvent))==1
    assert db.scalar(select(func.count()).select_from(ReleaseEventSeries))==2
    cal.rows[0].at+=timedelta(hours=1)
    refresh_calendar(db,cal,NOW+timedelta(days=1))
    assert db.scalar(select(func.count()).select_from(ScheduleChange))==1
    refresh_calendar(db,cal,NOW+timedelta(days=1))
    assert db.scalar(select(func.count()).select_from(ScheduleChange))==1

def test_provider_failure_preserves_last_verified_then_recovers(db):
    _,_,cal=setup_event(db)
    class Broken(CalendarFixture):
        def fetch(self):raise RuntimeError('private credential must not appear')
    state=refresh_calendar(db,Broken(),NOW+timedelta(hours=1))
    assert state.status=='PARTIAL' and aware(state.last_success_at)==NOW
    assert 'credential' not in state.last_error
    assert db.scalar(select(func.count()).select_from(ReleaseEvent))==1
    assert refresh_calendar(db,cal,NOW+timedelta(hours=2)).status=='OK'

def test_new_release_detection_and_idempotence(db,client):
    event,provider,_=setup_event(db)
    provider.rows.insert(0,Datum(date(NEW_PERIOD.year-1,NEW_PERIOD.month,1),Decimal('100'),'100'))
    provider.rows += [Datum(NEW_PERIOD,Decimal('102'),'102')]
    now=datetime(2027,3,15,14,tzinfo=UTC)
    # sync's captured_at is real wall time; explicitly set the test's logical due time before it.
    event.scheduled_at=datetime.now(UTC)-timedelta(minutes=10);event.scheduled_date=date.today();db.commit()
    assert run_job(db,event.id,provider,Settings(_env_file=None),datetime.now(UTC))
    assert event.status=='Released' and event.actual_released_at is None
    assert db.scalar(select(func.count()).select_from(ReleaseObservation))==2
    card=next(c for c in client.get('/api/v1/overview').json()['cards'] if c['series']['id']=='PCEPI')
    assert card['value']==2 and card['observation_date']==NEW_PERIOD.isoformat()
    assert client.get('/api/v1/calendar?status=Released&confirmed_only=true').json()['count']==1
    assert not run_job(db,event.id,provider,Settings(_env_file=None),datetime.now(UTC))
    assert db.scalar(select(func.count()).select_from(ReleaseObservation))==2

def test_no_new_data_not_released_and_restart_recovers(db):
    event,provider,_=setup_event(db);now=datetime.now(UTC)
    event.scheduled_at=now-timedelta(minutes=10);event.scheduled_date=now.date()
    job=db.get(ReleaseMonitorJob,event.id);job.status='running';job.lease_until=now-timedelta(seconds=1);job.next_retry_at=now-timedelta(seconds=1);db.commit()
    assert not run_job(db,event.id,provider,Settings(_env_file=None),now)
    assert event.status!='Released' and job.status=='waiting' and job.attempts==1
    assert job.next_retry_at>now.replace(tzinfo=None) if job.next_retry_at.tzinfo is None else job.next_retry_at>now

def test_active_lease_skips_second_worker(db):
    event,provider,_=setup_event(db);job=db.get(ReleaseMonitorJob,event.id)
    job.lease_until=NOW+timedelta(hours=1);db.commit()
    assert not run_job(db,event.id,provider,Settings(_env_file=None),NOW)
    assert job.attempts==0

def test_local_revision_diff_and_repeat(db):
    p=DataFixture();sync_series(db,p,'PCEPI');p.rows=[Datum(BASE_PERIOD,Decimal('101'),'101')]
    sync_series(db,p,'PCEPI');sync_series(db,p,'PCEPI')
    r=db.scalar(select(ObservationRevision))
    assert (r.old_value,r.new_value,r.delta)==(100,101,1) and r.scope=='local_sync_diff'
    assert db.scalar(select(func.count()).select_from(ObservationRevision))==1

def test_calendar_api_filters_validation_and_details(client,db):
    event,_,_=setup_event(db)
    response=client.get(f'/api/v1/calendar?start={NOW.date()}&end={(NOW+timedelta(days=40)).date()}&agency=bea&category=inflation')
    assert response.status_code==200 and response.json()['count']==1
    row=response.json()['events'][0]
    assert len(row['indicators'])==2 and row['indicators'][0]['actual'] is None
    assert row['revision_count']==0
    assert client.get('/api/v1/releases/'+event.id).json()['source_name']=='BEA'
    assert client.get('/api/v1/releases/'+event.id+'/observations').json()['observations']==[]
    assert client.get('/api/v1/monitor/status').json()['providers'][0]['status']=='OK'
    for query in ('agency=invalid','tz=invalid','limit=0','start=2027-02-01&end=2027-01-01'):
        r=client.get('/api/v1/calendar?'+query);assert r.status_code==422 and 'error' in r.json()
    assert client.get('/api/v1/releases/'+'0'*64).status_code==404

def test_reference_period_and_polling():
    assert reference_date('3rd Quarter 2026')==date(2026,7,1)
    assert reference_date('October 2026')==date(2026,10,1)
    s=Settings(_env_file=None)
    assert polling_delay(90000,s)>polling_delay(3600,s)>polling_delay(0,s)

def test_future_schedule_does_not_poll_fred(db):
    event,provider,_=setup_event(db)
    class MustNotFetch(DataFixture):
        def observations(self,*args):raise AssertionError('Premature FRED check')
    assert not run_job(db,event.id,MustNotFetch(),Settings(_env_file=None),NOW)
    job=db.get(ReleaseMonitorJob,event.id)
    assert job.attempts==0 and job.status=='waiting'

def test_monitor_failure_backoff_and_recovery(db):
    event,provider,_=setup_event(db);now=datetime.now(UTC)
    event.scheduled_at=now-timedelta(minutes=10);event.scheduled_date=now.date();db.commit()
    class Broken(DataFixture):
        def observations(self,*args):raise RuntimeError('private-key')
    assert not run_job(db,event.id,Broken(),Settings(_env_file=None),now)
    job=db.get(ReleaseMonitorJob,event.id)
    assert job.status=='failed' and 'private-key' not in job.last_error
    retry=aware(job.next_retry_at);assert retry>now
    job.next_retry_at=now;db.commit()
    provider.rows += [Datum(NEW_PERIOD,Decimal('102'),'102')]
    assert run_job(db,event.id,provider,Settings(_env_file=None),datetime.now(UTC))

def test_wrong_reference_period_never_confirms(db):
    event,provider,_=setup_event(db);now=datetime.now(UTC)
    event.scheduled_at=now-timedelta(minutes=10);event.scheduled_date=now.date()
    event.reference_period='January 1990';db.commit()
    provider.rows += [Datum(NEW_PERIOD,Decimal('102'),'102')]
    assert not run_job(db,event.id,provider,Settings(_env_file=None),now)
    assert event.status!='Released'

def test_old_confirmation_window_expires_without_backfill(db):
    event,provider,_=setup_event(db);now=datetime.now(UTC)
    event.scheduled_at=now-timedelta(days=8);event.scheduled_date=now.date();db.commit()
    assert not run_job(db,event.id,provider,Settings(_env_file=None),now)
    assert db.get(ReleaseMonitorJob,event.id).status=='expired'
    assert event.status=='Unknown'

def test_historical_event_does_not_use_current_value_as_previous(client,db):
    event,_,_=setup_event(db)
    event.scheduled_at=NOW-timedelta(days=30);event.scheduled_date=event.scheduled_at.date();db.commit()
    data=client.get('/api/v1/releases/'+event.id).json()
    assert all(i['previous'] is None and i['actual'] is None for i in data['indicators'])

def test_future_job_refreshes_pre_release_baseline(db):
    event,provider,_=setup_event(db)
    provider.rows += [Datum(NEW_PERIOD,Decimal('102'),'102')]
    for sid in ('PCEPI','PCEPILFE'):sync_series(db,provider,sid)
    assert not run_job(db,event.id,provider,Settings(_env_file=None),datetime.now(UTC))
    assert all(l.baseline_date==NEW_PERIOD for l in db.scalars(select(ReleaseEventSeries)))

def test_explicit_same_period_revision_keeps_pre_revision_value(db):
    event,provider,_=setup_event(db);now=datetime.now(UTC)
    event.scheduled_at=now-timedelta(minutes=10);event.scheduled_date=now.date()
    event.reference_period=BASE_PERIOD.strftime('%B %Y');db.commit()
    provider.rows=[Datum(BASE_PERIOD,Decimal('101'),'101')]
    assert run_job(db,event.id,provider,Settings(_env_file=None),now)
    snapshot=db.scalar(select(ReleaseObservation))
    assert snapshot.previous_value==100 and snapshot.value==101

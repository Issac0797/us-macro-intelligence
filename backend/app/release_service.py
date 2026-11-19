import hashlib
import json
import re
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from sqlalchemy import select, update, or_
from app.models import Series, Observation, utcnow
from app.release_models import ReleaseEvent, ReleaseEventSeries, ReleaseObservation, ObservationRevision, ReleaseMonitorJob, ScheduleChange, CalendarProviderState
from app.sync import insert_statement, latest_observations, sync_series

def aware(dt):
    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)) if dt else None

EXTRA_SERIES = [
    ('CES0500000003','Hourly earnings','Average Hourly Earnings of All Employees, Total Private','labor','Dollars per Hour','level','raw'),
    ('JTSJOL','JOLTS openings','Job Openings: Total Nonfarm','labor','Thousands','level','raw'),
    ('RSAFS','Retail sales','Advance Retail Sales: Retail Trade and Food Services','growth','Millions of Dollars','level','mom'),
    ('INDPRO','Industrial production','Industrial Production: Total Index','growth','Index 2017=100','index','mom'),
]

def seed_extended(session):
    for sid,short,title,category,units,kind,default in EXTRA_SERIES:
        values=dict(id=sid,short_name=short,title=title,category=category,units=units,unit_kind=kind,
                    default_transform=default,frequency='monthly',seasonal_adjustment='SA',agency={'labor':'U.S. Bureau of Labor Statistics','growth':'U.S. Census Bureau' if sid=='RSAFS' else 'Federal Reserve Board'}[category],source='FRED',source_url=f'https://fred.stlouisfed.org/series/{sid}')
        session.execute(insert_statement(session,Series).values(**values).on_conflict_do_nothing(index_elements=['id']))
    session.commit()

def refresh_calendar(session, provider, now=None):
    now=now or utcnow()
    state=session.get(CalendarProviderState,provider.name)
    if not state:
        state=CalendarProviderState(provider=provider.name,status='UNKNOWN',source_url=provider.url,last_attempt_at=now,event_count=0)
        session.add(state)
    state.last_attempt_at=now
    try:
        rows=provider.fetch()  # Parse entire document before changing verified data.
        if not rows: raise ValueError('Empty calendar')
    except Exception as exc:
        state.status='PARTIAL' if state.last_success_at else 'BLOCKED'
        state.last_error=f'{type(exc).__name__}: official source unavailable or schema changed'
        session.commit()
        return state
    for row in rows:
        official_released=row.released and row.day<=now.date()
        event_id=hashlib.sha256(f'{provider.name}|{row.key}'.encode()).hexdigest()
        event=session.get(ReleaseEvent,event_id)
        snapshot=dict(release_name=row.name,scheduled_date=row.day.isoformat(),scheduled_at=row.at.isoformat() if row.at else None,reference_period=row.period,source_url=row.url or provider.url)
        if not event:
            event=ReleaseEvent(id=event_id,provider=provider.name,source_key=row.key,category=row.category,importance=row.importance,
                release_name=row.name,scheduled_date=row.day,scheduled_at=row.at,reference_period=row.period,
                source_url=row.url or provider.url,source_name={'bls':'BLS','bea':'BEA','census':'Census Bureau','federal_reserve':'Federal Reserve','g17':'Federal Reserve G.17'}[provider.name],
                last_verified_at=now,status='Released' if official_released else 'Scheduled' if row.at and row.at>now else 'Unknown')
            session.add(event);session.flush()
            for sid in row.series:
                previous=session.scalar(latest_observations(session,sid).order_by(None).order_by(Observation.observation_date.desc()).limit(1)) if row.at and row.at>=now else None
                session.add(ReleaseEventSeries(event_id=event_id,series_id=sid,baseline_date=previous.observation_date if previous else None,baseline_version=previous.version if previous else None))
            # Historical imports have no trustworthy pre-release snapshot; do not backfill claims.
            jobstatus='waiting' if row.at and row.at>=now and row.series else 'unsupported'
            session.add(ReleaseMonitorJob(event_id=event_id,status=jobstatus,attempts=0,next_retry_at=now,
                last_error='No pre-release baseline or exact official time; automatic confirmation unavailable' if jobstatus=='unsupported' else None))
        else:
            # A date-only calendar must not erase a verified time from a published Fed document.
            if row.at is None and row.released and event.scheduled_at is not None:
                row.at=aware(event.scheduled_at);snapshot['scheduled_at']=row.at.isoformat()
            old=dict(release_name=event.release_name,scheduled_date=event.scheduled_date.isoformat(),scheduled_at=aware(event.scheduled_at).isoformat() if event.scheduled_at else None,reference_period=event.reference_period,source_url=event.source_url)
            if old!=snapshot:
                session.add(ScheduleChange(event_id=event_id,old_snapshot=json.dumps(old),new_snapshot=json.dumps(snapshot),detected_at=now))
                event.release_name,event.scheduled_date,event.scheduled_at,event.reference_period,event.source_url=row.name,row.day,row.at,row.period,row.url or provider.url
                job=session.get(ReleaseMonitorJob,event_id)
                if job.status not in ('confirmed','unsupported'):
                    job.next_retry_at=now
            if official_released: event.status='Released'
            event.last_verified_at=now
    seen={hashlib.sha256(f'{provider.name}|{r.key}'.encode()).hexdigest() for r in rows}
    for old_event in session.scalars(select(ReleaseEvent).where(ReleaseEvent.provider==provider.name,ReleaseEvent.scheduled_date>=now.date(),ReleaseEvent.status!='Released')):
        if old_event.id not in seen and old_event.status!='Unknown':
            session.add(ScheduleChange(event_id=old_event.id,old_snapshot=json.dumps({'status':old_event.status}),new_snapshot=json.dumps({'presence':'absent_from_latest_official_schedule'}),detected_at=now))
            old_event.status='Unknown'
            old_job=session.get(ReleaseMonitorJob,old_event.id)
            old_job.status='unsupported';old_job.last_error='Event absent from latest official schedule; retained for review'
    state.status='PARTIAL' if provider.name=='federal_reserve' else 'OK'
    state.last_success_at=now;state.last_error='Future statement/minutes times are not supplied; meeting dates only.' if provider.name=='federal_reserve' else None
    state.event_count=len({r.key for r in rows})
    session.commit()
    return state

def polling_delay(seconds_until,settings):
    if seconds_until>86400: return settings.monitor_far_seconds
    if seconds_until>900: return settings.monitor_day_seconds
    return settings.monitor_near_seconds

def reference_date(period):
    if not period: return None
    match=re.search(r'(\d)(?:st|nd|rd|th)? Quarter\s+(\d{4})',period,re.I)
    if match and 1<=int(match[1])<=4: return date(int(match[2]),(int(match[1])-1)*3+1,1)
    match=re.search(r'([A-Z][a-z]+)\s+(\d{4})',period)
    if match:
        try: return datetime.strptime(match[0],'%B %Y').date().replace(day=1)
        except ValueError: pass
    return None

def run_job(session,event_id,provider,settings,now=None):
    now=now or utcnow()
    # Durable lease is claimed atomically. Expired running jobs survive process restarts.
    claim=session.execute(update(ReleaseMonitorJob).where(ReleaseMonitorJob.event_id==event_id,
        ReleaseMonitorJob.status.in_(['waiting','running','failed']),ReleaseMonitorJob.next_retry_at<=now,
        or_(ReleaseMonitorJob.lease_until.is_(None),ReleaseMonitorJob.lease_until<=now)).values(status='running',lease_until=now+timedelta(seconds=settings.monitor_lease_seconds)).returning(ReleaseMonitorJob.event_id).execution_options(synchronize_session='fetch')).scalar_one_or_none()
    session.commit()
    if not claim: return False
    event=session.get(ReleaseEvent,event_id);job=session.get(ReleaseMonitorJob,event_id)
    due=aware(event.scheduled_at)
    if not due:
        job.status='unsupported';job.lease_until=None;session.commit();return False
    seconds=(due-now).total_seconds()
    if -seconds>settings.monitor_expire_seconds:
        event.status='Unknown';job.status='expired';job.last_error='Confirmation window expired; manual review required';job.lease_until=None;session.commit();return False
    if seconds>0:
        for link in session.scalars(select(ReleaseEventSeries).where(ReleaseEventSeries.event_id==event_id)):
            previous=session.scalar(latest_observations(session,link.series_id).where(Observation.value.is_not(None)).order_by(None).order_by(Observation.observation_date.desc()).limit(1))
            if previous and aware(previous.collected_at)<=now:
                link.baseline_date,link.baseline_version=previous.observation_date,previous.version
        job.status='waiting';job.next_retry_at=min(due,now+timedelta(seconds=polling_delay(seconds,settings)));job.lease_until=None;session.commit();return False
    job.attempts+=1;session.commit()
    from app.vintage_models import ReleaseMonitorAudit
    audit=ReleaseMonitorAudit(event_id=event_id,scheduled_at=due,check_started_at=utcnow(),attempts=job.attempts,status='running',updated_rows=0)
    session.add(audit);session.commit();audit_id=audit.id
    try:
        links=list(session.scalars(select(ReleaseEventSeries).where(ReleaseEventSeries.event_id==event_id)))
        confirmed=0
        for link in links:
            if session.get(ReleaseObservation,(event_id,link.series_id)):
                confirmed+=1;continue
            synced=sync_series(session,provider,link.series_id,settings=settings)
            audit.updated_rows+=synced.rows_inserted
            if synced.rows_inserted and not audit.first_detected_at:audit.first_detected_at=utcnow()
            session.commit()
            rows=list(session.scalars(latest_observations(session,link.series_id)))
            latest=next((r for r in reversed(rows) if r.value is not None),None)
            series=session.get(Series,link.series_id)
            # Only a new statistical period relative to a pre-release baseline proves new data.
            # Revision-only releases remain unconfirmed without explicit matching reference period.
            new_period=latest and link.baseline_date and latest.observation_date>link.baseline_date
            expected=reference_date(event.reference_period)
            matching=latest and (not expected or latest.observation_date==expected)
            revised_period=latest and expected==latest.observation_date and link.baseline_date==latest.observation_date and latest.version!=link.baseline_version
            updated=series.source_updated_at and aware(series.source_updated_at)>=due
            if latest and (new_period or revised_period) and matching and updated and aware(latest.collected_at)>=due and latest.observation_date<event.scheduled_date:
                previous=session.scalar(select(Observation).where(Observation.series_id==link.series_id,
                    Observation.observation_date==link.baseline_date,Observation.version==link.baseline_version).limit(1))
                session.execute(insert_statement(session,ReleaseObservation).values(event_id=event_id,series_id=link.series_id,
                    observation_date=latest.observation_date,value=latest.value,previous_value=previous.value if previous else None,
                    version=latest.version,units=latest.units,source=latest.source,captured_at=now).on_conflict_do_nothing(index_elements=['event_id','series_id']))
                confirmed+=1
        if links and confirmed==len(links):
            event.status='Released';event.detected_at=now;job.status='confirmed';job.last_error=None
        elif (now-due).total_seconds()>settings.monitor_expire_seconds:
            event.status='Unknown';job.status='expired';job.last_error='No complete post-schedule evidence; manual review required'
        else:
            event.status='Delayed' if (now-due).total_seconds()>settings.monitor_delay_seconds else 'Scheduled'
            job.status='waiting';job.next_retry_at=now+timedelta(seconds=settings.monitor_near_seconds)
        job.lease_until=None;audit.status=job.status;audit.check_finished_at=utcnow();session.commit();return job.status=='confirmed'
    except Exception as exc:
        session.rollback();job=session.get(ReleaseMonitorJob,event_id)
        job.status='failed';job.last_error=f'{type(exc).__name__}: release check failed'
        job.next_retry_at=now+timedelta(seconds=min(settings.monitor_far_seconds,settings.monitor_near_seconds*2**min(job.attempts,8)))
        job.lease_until=None
        audit=session.get(ReleaseMonitorAudit,audit_id);audit.status='failed';audit.error=job.last_error;audit.check_finished_at=utcnow()
        session.commit();return False

from datetime import date,datetime,time,timedelta,timezone
from typing import Annotated,Literal
from zoneinfo import ZoneInfo
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Query,Path
from sqlalchemy import select,func,or_,and_,inspect
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Series,Observation,utcnow
from app.release_models import ReleaseEvent,ReleaseEventSeries,ReleaseObservation,ObservationRevision,ReleaseMonitorJob,ScheduleChange,CalendarProviderState
from app.release_service import aware

router=APIRouter(prefix='/api/v1',tags=['releases'])
DB=Annotated[Session,Depends(get_db)]
Category=Literal['inflation','labor','growth','monetary']
Agency=Literal['bls','bea','census','federal_reserve','g17']
Status=Literal['Scheduled','Released','Delayed','Unknown']
EventID=Annotated[str,Path(pattern=r'^[a-f0-9]{64}$')]

def record(obj):
    result={}
    for col in inspect(type(obj)).columns:
        v=getattr(obj,col.key)
        result[col.key]=aware(v).isoformat() if isinstance(v,datetime) else v.isoformat() if isinstance(v,date) else float(v) if isinstance(v,Decimal) else v
    return result

def event_record(db,event):
    data=record(event); indicators=[]
    for link in db.scalars(select(ReleaseEventSeries).where(ReleaseEventSeries.event_id==event.id)):
        series=db.get(Series,link.series_id);actual=db.get(ReleaseObservation,(event.id,link.series_id))
        baseline=db.scalar(select(Observation).where(Observation.series_id==link.series_id,Observation.observation_date==link.baseline_date,Observation.version==link.baseline_version).limit(1)) if link.baseline_version else None
        if baseline and (not event.scheduled_at or aware(baseline.collected_at)>aware(event.scheduled_at)):
            baseline=None  # Never label a post-event snapshot as a historical previous value.
        indicators.append(dict(series_id=series.id,title=series.short_name,units=actual.units if actual else series.units,
            previous=float(actual.previous_value) if actual and actual.previous_value is not None else float(baseline.value) if baseline and baseline.value is not None else None,
            actual=float(actual.value) if actual and actual.value is not None else None,
            observation_date=actual.observation_date.isoformat() if actual else None,
            captured_at=aware(actual.captured_at).isoformat() if actual else None))
    data['indicators']=indicators
    data['revision_count']=db.scalar(select(func.count()).select_from(ObservationRevision).where(
        ObservationRevision.series_id.in_([i['series_id'] for i in indicators]),
        ObservationRevision.detected_at>=event.scheduled_at,ObservationRevision.detected_at<=event.detected_at)) if event.scheduled_at and event.detected_at else 0
    data['time_precision']='minute' if event.scheduled_at else 'date_only'
    data['time_status']='Time Confirmed' if event.scheduled_at else 'Date Confirmed / Time Unknown'
    from app.vintage_models import VintageArchive,VintageObservation
    from app.release_service import reference_date
    reference=reference_date(event.reference_period)
    data['reference_observation_date']=reference.isoformat() if reference else None
    data['vintage_availability']={i['series_id']:bool((a:=db.get(VintageArchive,i['series_id'])) and a.status=='complete' and (reference is None or db.scalar(select(VintageObservation.observation_date).where(VintageObservation.series_id==i['series_id'],VintageObservation.observation_date==reference,VintageObservation.value.is_not(None)).limit(1)) is not None)) for i in indicators}
    data['revision_scope']='local_sync_diff; not ALFRED; detection is not official release time'
    return data

@router.get('/calendar')
def calendar(db:DB,start:date|None=None,end:date|None=None,category:Category|None=None,agency:Agency|None=None,
    status:Status|None=None,importance:Literal['high','medium','low']|None=None,
    tz:Literal['America/New_York','Asia/Shanghai','UTC']='America/New_York',limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),order:Literal['asc','desc']='asc',confirmed_only:bool=False):
    if start and end and start>end: raise HTTPException(422,'start must not be later than end')
    q=select(ReleaseEvent)
    if confirmed_only: q=q.where(ReleaseEvent.id.in_(select(ReleaseObservation.event_id)))
    if start:
        boundary=datetime.combine(start,time.min,ZoneInfo(tz)).astimezone(timezone.utc)
        q=q.where(or_(ReleaseEvent.scheduled_at>=boundary,and_(ReleaseEvent.scheduled_at.is_(None),ReleaseEvent.scheduled_date>=start)))
    if end:
        boundary=datetime.combine(end+timedelta(days=1),time.min,ZoneInfo(tz)).astimezone(timezone.utc)
        q=q.where(or_(ReleaseEvent.scheduled_at<boundary,and_(ReleaseEvent.scheduled_at.is_(None),ReleaseEvent.scheduled_date<=end)))
    for column,value in [(ReleaseEvent.category,category),(ReleaseEvent.provider,agency),(ReleaseEvent.status,status),(ReleaseEvent.importance,importance)]:
        if value: q=q.where(column==value)
    count=db.scalar(select(func.count()).select_from(q.subquery()))
    rows=db.scalars(q.order_by(ReleaseEvent.scheduled_date.desc() if order=='desc' else ReleaseEvent.scheduled_date,ReleaseEvent.scheduled_at,ReleaseEvent.id).offset(offset).limit(limit))
    return dict(count=count,offset=offset,limit=limit,events=[event_record(db,e) for e in rows],providers=[record(s) for s in db.scalars(select(CalendarProviderState))],generated_at=utcnow())

@router.get('/calendar/upcoming')
def upcoming(db:DB,limit:int=Query(5,ge=1,le=50)):
    now=utcnow();today=now.astimezone(ZoneInfo('America/New_York')).date()
    q=select(ReleaseEvent).where(ReleaseEvent.status!='Released',ReleaseEvent.importance=='high',
        or_(ReleaseEvent.scheduled_at>=now,and_(ReleaseEvent.scheduled_at.is_(None),ReleaseEvent.scheduled_date>=today))).order_by(ReleaseEvent.scheduled_date,ReleaseEvent.scheduled_at).limit(limit)
    return {'events':[event_record(db,e) for e in db.scalars(q)]}

@router.get('/releases/{event_id}')
def release_detail(event_id:EventID,db:DB):
    event=db.get(ReleaseEvent,event_id)
    if not event: raise HTTPException(404,'Release event not found')
    result=event_record(db,event)
    job=db.get(ReleaseMonitorJob,event_id)
    result['monitor']=record(job) if job else None
    result['schedule_changes']=[record(c) for c in db.scalars(select(ScheduleChange).where(ScheduleChange.event_id==event_id).order_by(ScheduleChange.detected_at))]
    ids=[i['series_id'] for i in result['indicators']]
    # Nearby detected revisions are evidence, not a causal attribution to the event.
    q=select(ObservationRevision).where(ObservationRevision.series_id.in_(ids))
    if event.scheduled_at: q=q.where(ObservationRevision.detected_at>=event.scheduled_at)
    if event.detected_at: q=q.where(ObservationRevision.detected_at<=event.detected_at)
    result['revisions']=[record(r) for r in db.scalars(q.order_by(ObservationRevision.detected_at.desc()).limit(50))] if event.detected_at else []
    return result

@router.get('/releases/{event_id}/observations')
def release_observations(event_id:EventID,db:DB):
    if not db.get(ReleaseEvent,event_id): raise HTTPException(404,'Release event not found')
    return {'observations':[record(o) for o in db.scalars(select(ReleaseObservation).where(ReleaseObservation.event_id==event_id))]}

@router.get('/revisions')
def revisions(db:DB,series_id:str|None=Query(None,pattern=r'^[A-Z0-9]{1,32}$'),start:date|None=None,end:date|None=None,limit:int=Query(50,ge=1,le=500),offset:int=Query(0,ge=0)):
    if start and end and start>end: raise HTTPException(422,'start must not be later than end')
    q=select(ObservationRevision)
    if series_id: q=q.where(ObservationRevision.series_id==series_id)
    if start: q=q.where(ObservationRevision.detected_at>=datetime.combine(start,time.min,timezone.utc))
    if end: q=q.where(ObservationRevision.detected_at<datetime.combine(end+timedelta(days=1),time.min,timezone.utc))
    return {'count':db.scalar(select(func.count()).select_from(q.subquery())),'revisions':[record(r) for r in db.scalars(q.order_by(ObservationRevision.detected_at.desc()).offset(offset).limit(limit))]}

@router.get('/monitor/status')
def monitor_status(db:DB):
    from app.vintage_models import ReleaseMonitorAudit
    evidence=db.scalar(select(func.count()).select_from(ReleaseMonitorAudit).where(ReleaseMonitorAudit.status=='confirmed',ReleaseMonitorAudit.updated_rows>0))
    return {'real_release_validation':'EVIDENCE_AVAILABLE_REQUIRES_REVIEW' if evidence else 'PENDING_REAL_RELEASE_VALIDATION',
        'series_sync':__import__('app.sync_schedule',fromlist=['sync_states']).sync_states(db),
        'release_audits':[record(a) for a in db.scalars(select(ReleaseMonitorAudit).order_by(ReleaseMonitorAudit.id.desc()).limit(50))],
        'providers':[record(s) for s in db.scalars(select(CalendarProviderState))],
        'job_counts':dict(db.execute(select(ReleaseMonitorJob.status,func.count()).group_by(ReleaseMonitorJob.status)).all()),
        'jobs':[record(j) for j in db.scalars(select(ReleaseMonitorJob).order_by(ReleaseMonitorJob.next_retry_at).limit(100))],
        'generated_at':utcnow(),'note':'Delayed means data not yet confirmed, not an official postponement. Importance is an editorial classification.'}

"""Point lookup without guessing release dates or loading whole revision archives."""
from datetime import date
from typing import Annotated,Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Series
from app.read_queries import observation_rows
from app.workspace_schemas import Day
from app.vintage_models import VintageArchive,VintageObservation
from app.vintage_queries import historical_metadata,PRECISION
from app.release_models import ReleaseObservation,ReleaseEvent
from app.fed.models import Meeting
from app.release_service import aware

router=APIRouter(prefix='/api/v1/workspace',tags=['Observation drill-down'])
@router.get('/observation-details')
def details(db:Annotated[Session,Depends(get_db)],series_id:str=Query(pattern=r'^[A-Z0-9]{1,32}$'),observation_date:Day=None,data_mode:Literal['latest','vintage']='latest',as_of:Day|None=None):
    if observation_date is None:raise HTTPException(422,'observation_date is required')
    if (data_mode=='vintage')!=(as_of is not None):raise HTTPException(422,'Vintage requires as_of; latest must not set it')
    series=db.get(Series,series_id)
    if not series:raise HTTPException(404,'Unknown series')
    archive=db.get(VintageArchive,series_id)
    available=bool(archive and archive.status=='complete' and archive.first_vintage)
    row=None;units=series.units;frequency=series.frequency;adjustment=series.seasonal_adjustment
    if data_mode=='vintage':
        available=available and archive.first_vintage<=as_of<=archive.covered_through
        if available:
            metadata=historical_metadata(db,series_id,as_of)
            if metadata:
                units,frequency,adjustment=metadata.units,metadata.frequency,metadata.seasonal_adjustment
                row=db.scalar(select(VintageObservation).where(VintageObservation.series_id==series_id,VintageObservation.observation_date==observation_date,VintageObservation.observation_date<=as_of,VintageObservation.vintage_date<=as_of,VintageObservation.realtime_end>=as_of))
    else:
        row=db.execute(observation_rows(db,series_id,start=observation_date,end=observation_date)).first()
    cutoff=as_of if data_mode=='vintage' else date.today()
    q=select(VintageObservation.vintage_date).where(VintageObservation.series_id==series_id,VintageObservation.observation_date==observation_date,VintageObservation.vintage_date<=cutoff)
    first=db.scalar(select(func.min(q.subquery().c.vintage_date))) if available else None
    last=db.scalar(select(func.max(q.subquery().c.vintage_date))) if available else None
    events=[]
    # Only independently captured observation↔event records are an exact relationship.
    captures=db.scalars(select(ReleaseObservation).where(ReleaseObservation.series_id==series_id,ReleaseObservation.observation_date==observation_date).order_by(ReleaseObservation.captured_at.desc()).limit(20)).all()
    for capture in captures:
        event=db.get(ReleaseEvent,capture.event_id)
        if not event or data_mode=='vintage' and (not event.actual_released_at or aware(event.actual_released_at).date()>as_of):continue
        meeting=db.scalar(select(Meeting).where(Meeting.calendar_event_id==event.id))
        events.append(dict(id=event.id,name=event.release_name,source_url=event.source_url,source_release_date=event.actual_released_at,meeting_id=meeting.id if meeting else None))
    return dict(series_id=series_id,name=series.title,observation_date=observation_date,value=float(row.value) if row and row.value is not None else None,raw_value=row.raw_value if row else None,
        units=units,frequency=frequency,seasonal_adjustment=adjustment,source='ALFRED' if data_mode=='vintage' else series.source,source_url=f'https://alfred.stlouisfed.org/series?seid={series_id}' if data_mode=='vintage' else series.source_url,
        data_mode=data_mode,as_of=as_of,vintage_date=row.vintage_date if row and data_mode=='vintage' else None,version=str(row.vintage_date) if row and data_mode=='vintage' else row.version if row else None,
        latest_successful_sync=aware(archive.retrieved_at) if data_mode=='vintage' and archive else aware(series.last_synced_at),retrieved_at=aware(row.retrieved_at if data_mode=='vintage' else row.collected_at) if row else None,
        status='AVAILABLE' if row else 'HISTORICAL_VINTAGE_UNAVAILABLE' if data_mode=='vintage' else 'NO_OBSERVATION',historical_available=bool(first),first_available_vintage=first,latest_available_vintage=last,
        initial_note='Earliest ALFRED archive is not certified official first release',source_release_date=events[0]['source_release_date'] if events else None,related_events=events,precision_note=PRECISION)

from datetime import date
from typing import Annotated,Literal
from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.db import get_db
from app.alfred import SUPPORTED
from app.vintage_models import SeriesVintage,VintageArchive,VintageSyncJob,VintageObservation
from app.vintage_queries import series_archive,snapshot,revision_data,summary_statistics,PRECISION
from app.transforms import Transform
from app.calendar_api import record
import re
from pydantic import BeforeValidator

def date_only(value):
    if isinstance(value,str) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('Date only; intraday timestamps unsupported')
    return value
DateOnly=Annotated[date,BeforeValidator(date_only)]

router=APIRouter(prefix='/api/v1',tags=['ALFRED vintages'])
DB=Annotated[Session,Depends(get_db)]
Page=Annotated[int,Query(ge=1,le=100000)]
PageSize=Annotated[int,Query(ge=1,le=1000)]

@router.get('/vintage-sync/status')
def status(db:DB):
    return dict(supported_series=SUPPORTED,archives=[record(a) for a in db.scalars(select(VintageArchive))],
        jobs=[{k:v for k,v in record(j).items() if k not in ('catalog_json','metadata_json')} for j in db.scalars(select(VintageSyncJob).order_by(VintageSyncJob.started_at.desc()).limit(50))],
        vintage_count=db.scalar(select(func.count()).select_from(SeriesVintage)),observation_interval_count=db.scalar(select(func.count()).select_from(VintageObservation)),precision_note=PRECISION)

@router.get('/vintages/{series_id}')
def vintages(series_id:str,db:DB,start:date|None=None,end:date|None=None,page:Page=1,page_size:PageSize=100):
    _,archive=series_archive(db,series_id)
    if start and end and start>end:raise HTTPException(422,'start must not exceed end')
    q=select(SeriesVintage).where(SeriesVintage.series_id==series_id)
    if start:q=q.where(SeriesVintage.vintage_date>=start)
    if end:q=q.where(SeriesVintage.vintage_date<=end)
    return dict(series_id=series_id,archive=record(archive) if archive else None,precision_note=PRECISION,count=db.scalar(select(func.count()).select_from(q.subquery())),page=page,page_size=page_size,vintages=[record(v) for v in db.scalars(q.order_by(SeriesVintage.vintage_date).offset((page-1)*page_size).limit(page_size))])

@router.get('/historical-snapshot')
def historical_snapshot(db:DB,series_id:str,as_of:DateOnly,transform:Transform=Transform.RAW,start:date|None=None,end:date|None=None,compare_as_of:DateOnly|None=None,
    frequency:Literal['monthly','quarterly','daily']|None=None,window:int=Query(3,ge=2,le=365),page:Page=1,page_size:PageSize=500):
    return snapshot(db,series_id,as_of,transform,start,end,window,frequency,page,page_size,compare_as_of)

@router.get('/vintages/{series_id}/observations')
def vintage_observations(series_id:str,db:DB,vintage_date:DateOnly|None=None,as_of:DateOnly|None=None,transform:Transform=Transform.RAW,start:date|None=None,end:date|None=None,compare_as_of:DateOnly|None=None,
    frequency:Literal['monthly','quarterly','daily']|None=None,window:int=Query(3,ge=2,le=365),page:Page=1,page_size:PageSize=500):
    if (vintage_date is None)==(as_of is None):raise HTTPException(422,'Supply exactly one vintage_date or as_of date')
    return snapshot(db,series_id,vintage_date or as_of,transform,start,end,window,frequency,page,page_size,compare_as_of)

@router.get('/revisions/{series_id}/summary')
def revision_summary(series_id:str,db:DB,start:date=Query(date(2020,1,1)),end:date|None=None,window_days:int|None=None,as_of:DateOnly|None=None):
    series,archive,rows=revision_data(db,series_id,start,end,window_days,as_of)
    data=summary_statistics(rows)
    data.update(series_id=series_id,archive=record(archive) if archive else None,window_days=window_days,requested_start=start,requested_end=end,
        heatmap=[{k:v for k,v in r.items() if k!='timeline'} for r in rows],precision_note=PRECISION)
    return data

@router.get('/revisions/{series_id}')
def revisions(series_id:str,db:DB,start:date|None=None,end:date|None=None,observation_date:date|None=None,window_days:int|None=None,page:Page=1,page_size:PageSize=100,as_of:DateOnly|None=None):
    if observation_date:start=end=observation_date
    series,archive,rows=revision_data(db,series_id,start,end,window_days,as_of)
    return dict(series_id=series_id,archive=record(archive) if archive else None,unit_kind=series.unit_kind,precision_note=PRECISION,count=len(rows),page=page,page_size=page_size,observations=rows[(page-1)*page_size:page*page_size])

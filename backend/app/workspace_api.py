from datetime import date
from typing import Annotated, Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.db import get_db
from app.models import Series, Observation, utcnow
from app.workspace_models import ChartWorkspace
from app.workspace_schemas import WorkspaceWrite, ChartConfiguration, Day
from app.workspace_engine import chart_data
from app.release_service import aware
from app.treasury import yield_curves, spread_history, curve_changes

from app.analytics.schemas import AnalyticsConfiguration
from app.workspace_schemas import StrictModel
from pydantic import Field
from app.dashboard_schemas import DashboardConfiguration
class ResearchWrite(StrictModel):
    name: str = Field(min_length=1,max_length=140)
    description: str = Field('',max_length=2000)
    configuration: ChartConfiguration | AnalyticsConfiguration | DashboardConfiguration

router=APIRouter(prefix='/api/v1',tags=['Research workspace'])
DB=Annotated[Session,Depends(get_db)]


def stored(row):
    try:config=(DashboardConfiguration if row.configuration.get('kind')=='dashboard' else AnalyticsConfiguration if row.configuration.get('kind')=='analytics' else ChartConfiguration).model_validate(row.configuration)
    except ValidationError:raise HTTPException(409,'Stored configuration version is unsupported or invalid; export and migrate explicitly') from None
    if row.configuration_version!=config.configuration_version:raise HTTPException(409,'Configuration version mismatch')
    return dict(id=row.id,name=row.name,description=row.description,configuration=config.model_dump(mode='json'),configuration_version=row.configuration_version,created_at=aware(row.created_at),updated_at=aware(row.updated_at))


def get_workspace(db,identifier):
    row=db.get(ChartWorkspace,str(identifier))
    if not row:raise HTTPException(404,'Workspace not found')
    return row


@router.get('/workspace/series/search')
def search(db:DB,q:str=Query('',max_length=100),category:Literal['inflation','labor','growth','interest_rates','financial_conditions']|None=None,page:int=Query(1,ge=1,le=10000),page_size:int=Query(30,ge=1,le=100)):
    query=select(Series)
    if q:
        escaped=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        term=f'%{escaped}%';query=query.where(or_(Series.id.ilike(term,escape='\\'),Series.title.ilike(term,escape='\\'),Series.short_name.ilike(term,escape='\\')))
    if category:query=query.where(Series.category.in_(['monetary','interest_rates']) if category=='interest_rates' else Series.category==category)
    count=db.scalar(select(func.count()).select_from(query.subquery()))
    result=[]
    for s in db.scalars(query.order_by(Series.id).offset((page-1)*page_size).limit(page_size)):
        result.append(dict(id=s.id,name=s.title,short_name=s.short_name,category=s.category,units=s.units,frequency=s.frequency,unit_kind=s.unit_kind,seasonal_adjustment=s.seasonal_adjustment,source=s.source,source_url=s.source_url,
            has_observations=db.scalar(select(Observation.id).where(Observation.series_id==s.id).limit(1)) is not None))
    return dict(series=result,count=count,page=page,page_size=page_size)


@router.post('/workspace/chart-data')
def data(configuration:ChartConfiguration,db:DB):return chart_data(db,configuration)


@router.get('/workspaces')
def list_workspaces(db:DB,page:int=Query(1,ge=1,le=10000),page_size:int=Query(50,ge=1,le=100)):
    rows=db.scalars(select(ChartWorkspace).order_by(ChartWorkspace.updated_at.desc()).offset((page-1)*page_size).limit(page_size))
    return dict(count=db.scalar(select(func.count()).select_from(ChartWorkspace)),page=page,page_size=page_size,
        workspaces=[dict(id=r.id,name=r.name,description=r.description,kind=r.configuration.get("kind","chart"),view=r.configuration.get("view","chart"),configuration_version=r.configuration_version,updated_at=aware(r.updated_at)) for r in rows])


@router.post('/workspaces',status_code=201)
def save(payload:ResearchWrite,db:DB):
    row=ChartWorkspace(id=str(uuid4()),name=payload.name,description=payload.description,configuration=payload.configuration.model_dump(mode='json'),configuration_version=payload.configuration.configuration_version)
    db.add(row);db.commit();return stored(row)


@router.get('/workspaces/{identifier}')
def load(identifier:UUID,db:DB):return stored(get_workspace(db,identifier))


@router.put('/workspaces/{identifier}')
def update(identifier:UUID,payload:ResearchWrite,db:DB):
    row=get_workspace(db,identifier);row.name=payload.name;row.description=payload.description;row.configuration=payload.configuration.model_dump(mode='json');row.configuration_version=payload.configuration.configuration_version;row.updated_at=utcnow();db.commit();return stored(row)


@router.delete('/workspaces/{identifier}')
def delete(identifier:UUID,db:DB):
    row=get_workspace(db,identifier);db.delete(row);db.commit();return dict(deleted=str(identifier))


@router.get('/yield-curve')
def curves(db:DB,dates:Annotated[list[Day]|None,Query()]=None,include_latest:bool=True,nearest_previous:bool=False):return yield_curves(db,dates or [],include_latest,nearest_previous)


@router.get('/yield-curve/spreads')
def spreads(db:DB,start:Day=date(2016,1,1),end:Day|None=None):return spread_history(db,start,end or date.today())


@router.get('/yield-curve/changes')
def changes(db:DB,start:Day,end:Day,nearest_previous:bool=False):return curve_changes(db,start,end,nearest_previous)


@router.post('/workspace/validate')
def validate_configuration(configuration:DashboardConfiguration|ChartConfiguration):
    return configuration.model_dump(mode='json')

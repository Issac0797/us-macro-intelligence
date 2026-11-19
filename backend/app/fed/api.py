from datetime import date
from typing import Annotated,Literal
from pydantic import BeforeValidator
from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.fed import queries as q
from app.fed.models import Document
from sqlalchemy import select
router=APIRouter(prefix='/api/v1/fed',tags=['Federal Reserve policy'])
DB=Annotated[Session,Depends(get_db)]
Year=Annotated[int|None,Query(ge=2024,le=2026)]
def valid_mid(v):
 try:
  d=date.fromisoformat(v)
  if d.year not in [2024,2025,2026]:raise ValueError()
 except (ValueError,TypeError):raise ValueError('A valid 2024–2026 ISO meeting date is required')
 return d.isoformat()
Mid=Annotated[str,BeforeValidator(valid_mid)]
def bounds(start,end):
 if start>end or (end-start).days>3653:raise HTTPException(422,'Range must be ordered and at most ten years')
@router.get('/overview')
def overview(db:DB):return q.overview(db)
@router.get('/meetings')
def meetings(db:DB,year:Year=None,page:int=Query(1,ge=1,le=100),page_size:int=Query(50,ge=1,le=100)):return q.meetings(db,year,page,page_size)
@router.get('/meetings/{mid}')
def meeting(mid:date,db:DB):
 m=q.get_meeting(db,mid.isoformat());r=q.record(m);r['documents']=[q.document(d,True) for d in db.scalars(select(Document).where(Document.meeting_id==m.id))];d=db.get(q.Decision,m.id);r['decision']=q.record(d) if d else None;return r
@router.get('/meetings/{mid}/documents')
def documents(mid:date,db:DB):
 q.get_meeting(db,mid.isoformat());return {'items':[q.document(d,True) for d in db.scalars(select(Document).where(Document.meeting_id==mid.isoformat()))]}
@router.get('/statements/compare')
def compare(db:DB,left:Mid,right:Mid):return q.compare(db,left,right)
@router.get('/projections')
def projections(db:DB,meeting_id:Mid|None=None,compare_to:Mid|None=None):return q.projections(db,meeting_id,compare_to)
@router.get('/dot-plot')
def dots(db:DB,meeting_id:Mid|None=None,compare_to:Mid|None=None):return q.dots(db,meeting_id,compare_to)
@router.get('/rates')
def rates(db:DB,start:date=date(2024,1,1),end:date|None=None):
 end=end or date.today();bounds(start,end);return q.rates(db,start,end)
@router.get('/rate-decisions')
def decisions(db:DB,start:date=date(2024,1,1),end:date|None=None):
 end=end or date.today();bounds(start,end);return q.decisions(db,start,end)
@router.get('/historical-snapshot')
def historical(db:DB,meeting_id:Mid,mode:Literal['pre','post']='pre',as_of:date|None=None):return q.historical(db,meeting_id,mode,as_of)
@router.get('/sync/status')
def status(db:DB):return q.status(db)

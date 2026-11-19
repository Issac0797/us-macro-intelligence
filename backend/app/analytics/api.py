from datetime import date
from typing import Annotated,Literal
from fastapi import APIRouter,Depends,Query,HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.analytics.schemas import AnalyticsConfiguration
from app.analytics.engine import analyze
from app.analytics.cycle import current,Thresholds
from app.workspace_schemas import Day
from app.treasury import spread_history
from app.workspace_engine import period_grid,recession_intervals
from types import SimpleNamespace
from app.bounded_cache import results,dataset_version
from app.diagnostics import phase

def reuse(db,key,fn):
    def compute():
        with phase('calculation'):return fn()
    return results.get(('cycle-v1',key,dataset_version(db)),compute,ttl=30)
def cached_analysis(db,c,operation):
    return reuse(db,('analytics',operation,c.model_dump_json()),lambda:analyze(db,c,operation))

router=APIRouter(prefix='/api/v1',tags=['Macro research analytics'])
DB=Annotated[Session,Depends(get_db)]
@router.post('/analytics/correlation')
def corr(c:AnalyticsConfiguration,db:DB):return cached_analysis(db,c,'correlation')
@router.post('/analytics/rolling-correlation')
def rolling(c:AnalyticsConfiguration,db:DB):return cached_analysis(db,c,'rolling-correlation')
@router.post('/analytics/lead-lag')
def lead(c:AnalyticsConfiguration,db:DB):return cached_analysis(db,c,'lead-lag')
@router.post('/analytics/rolling-statistics')
def stats(c:AnalyticsConfiguration,db:DB):return cached_analysis(db,c,'rolling-statistics')
@router.get('/analytics/metadata')
def metadata():return dict(methods=['pearson','spearman'],rules=Thresholds().model_dump(),lag_definition='Corr(X_t,Y_t+k), positive k: X leads Y',rolling='Trailing windows only, standard deviation ddof=0; percentile includes current, counts <= current',minimum_samples=3,precision='date only',warnings=['No causal or predictive conclusion','Nonstationarity, serial dependence and multiple lag searches require independent research validation'])
def params(data_mode,as_of):
    if data_mode=='vintage' and as_of is None:raise HTTPException(422,'Vintage requires as_of')
    if data_mode=='latest' and as_of is not None:raise HTTPException(422,'Latest must not set as_of')
    return as_of or date.today()
@router.get('/business-cycle/current')
def now(db:DB,data_mode:Literal['latest','vintage']='latest',as_of:Day|None=None,rules:Annotated[Thresholds,Depends()]=None):
    at=params(data_mode,as_of);r=rules or Thresholds()
    def compute():
        from datetime import timedelta
        cache={}
        previous=current(db,data_mode,at.replace(day=1)-timedelta(days=1),r,cache=cache)
        return current(db,data_mode,at,r,previous['state'],cache)
    return reuse(db,('current',data_mode,at,r.model_dump_json()),compute)
@router.get('/business-cycle/history')
def history(db:DB,start:Day=date(2023,1,1),end:Day|None=None,data_mode:Literal['latest','vintage']='latest',as_of:Day|None=None,show_ex_post_recessions:bool=False,rules:Annotated[Thresholds,Depends()]=None):
    limit=params(data_mode,as_of);end=min(end or limit,limit)
    if start>end or (end-start).days>366*5:raise HTTPException(422,'History range must be ordered and at most five years')
    def compute():
        rows=[];previous=None;cache={}
        for d in period_grid(start,end,'monthly'):
            result=current(db,data_mode,d,rules or Thresholds(),previous,cache);rows.append(result);previous=result['state']
        rec=[]
        if show_ex_post_recessions:rec,_=recession_intervals(db,SimpleNamespace(show_recessions=True,data_mode='latest',start=start),end)
        return dict(history=rows,recent_three=rows[-3:],recessions=rec,recession_note='Ex-post USREC reference; not contemporaneously known',data_mode=data_mode,as_of=as_of,rule_version='cycle-v1')
    return reuse(db,('history',start,end,data_mode,as_of,show_ex_post_recessions,(rules or Thresholds()).model_dump_json()),compute)
@router.get('/recession-indicators')
def recession(db:DB,start:Day=date(2020,1,1),end:Day|None=None,data_mode:Literal['latest','vintage']='latest',as_of:Day|None=None,rules:Annotated[Thresholds,Depends()]=None):
    at=params(data_mode,as_of)
    def compute():
        at=params(data_mode,as_of);result=current(db,data_mode,at,rules or Thresholds())
        if data_mode=='latest':
            spreads=spread_history(db,start,min(end or at,at))
            for s in spreads['spreads']:
                for r in s['inversion_intervals']:r['calendar_duration_days']=(r['end']-r['start']).days+1
            result['inversions']=spreads
        else:result['inversions']={'status':'HISTORICAL_VINTAGE_UNAVAILABLE','note':'Treasury archives not collected; latest inversion history not substituted'}
        return result
    return reuse(db,('recession',start,end,data_mode,as_of,at,(rules or Thresholds()).model_dump_json()),compute)

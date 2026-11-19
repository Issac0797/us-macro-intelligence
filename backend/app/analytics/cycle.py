from datetime import date
from fastapi import HTTPException
from statistics import mean
from pydantic import Field
from app.workspace_schemas import StrictModel
from app.workspace_engine import native_history,transform_points
from app.workspace_schemas import Calculation
from app.analytics.statistics import sahm
from app.treasury import spread_history

class Thresholds(StrictModel):
    rule_version: str = Field('cycle-v1',pattern='^cycle-v1$')
    inflation: float = Field(3,ge=0,le=20)
    unemployment_change: float = Field(.3,ge=0,le=5)
    payroll: float = Field(50,ge=-1000,le=1000)
    growth: float = Field(0,ge=-20,le=20)
    inversion: float = Field(0,ge=-5,le=5)
    sahm: float = Field(.5,ge=0,le=5)
    claims_change: float = Field(0,ge=-1000000,le=1000000)

SIGNALS=[('inflation','PCEPILFE','Core PCE YoY',['yoy']),('inflation','PCEPILFE','Core PCE 3M',['annualized_3m']),('inflation','CPIAUCSL','CPI YoY',['yoy']),('labor','UNRATE','Unemployment',['raw']),('labor','PAYEMS','Payroll change MA3',['absolute_change','moving_average']),('labor','ICSA','Initial claims',['raw']),('growth','GDPC1','Real GDP annualized',['annualized_3m']),('growth','INDPRO','Industrial production YoY',['yoy']),('growth','RSAFS','Retail sales YoY',['yoy']),('financial','DGS10','10Y-2Y',['raw']),('financial','DGS10','10Y-3M',['raw']),('financial','DFF','Fed funds',['raw'])]

def classify(scores,previous=None):
    if any(scores.get(d) is None for d in ('inflation','labor','growth','financial')):return 'Insufficient Data'
    real=(scores['labor']+scores['growth'])/2
    if real<0:return 'Contraction'
    if previous=='Contraction' and real>=0:return 'Recovery'
    if real==0 or scores['financial']<0 or scores['inflation']<0:return 'Slowdown'
    return 'Expansion'

def current(db,mode,at,rules,previous=None,cache=None):
    cache={} if cache is None else cache
    def load(sid):
        key=(sid,mode,at if mode=="vintage" else None)
        if key not in cache:
            try:cache[key]=native_history(db,sid,mode,at)
            except HTTPException as exc:
                if exc.status_code!=404:raise
                cache[key]=(None,[],dict(status='NEEDS_SYNC',series_id=sid,message='Metadata or history not initialized'))
        return cache[key]
    signals=[];groups={d:[] for d in ('inflation','labor','growth','financial')};unrate=[];unrate_info={}
    for dim,sid,name,ops in SIGNALS:
        from app.diagnostics import checkpoint
        checkpoint()
        spec,points,info=load(sid);value=change=period=None;units=None;threshold=None;score=None
        if spec:
            if sid=='UNRATE':unrate=points;unrate_info=info
            conversion_key=('converted',sid,mode,at if mode=='vintage' else None,tuple(ops))
            if conversion_key not in cache:
                cache[conversion_key]=transform_points(spec,points,[Calculation(transform=op,window=3) for op in ops])
            spec,converted=cache[conversion_key];valid=[p for p in converted if p['value'] is not None and p['date']<=at]
            history_valid=valid
            # Staleness check in native statistical periods, not fabricated availability dates.
            valid=[p for p in valid if (at-p['date']).days<=({'daily':14,'weekly':28,'monthly':100,'quarterly':200}[spec.frequency])]
            if valid:
                p=valid[-1];value=float(p['value']);period=p['date'];units=spec.units
                change=float(p['value']-history_valid[-2]['value']) if len(history_valid)>1 else None
                if name.startswith('10Y-'):
                    rhs='DGS2' if name=='10Y-2Y' else 'DGS3MO';_,right,_=load(rhs);right={p['date']:p['value'] for p in right};pairs=[p for p in valid if p['date'] in right and right[p['date']] is not None]
                    if pairs:p=pairs[-1];value=float(p['value']-right[p['date']]);period=p['date'];units='Percentage points';change=value-float(pairs[-2]['value']-right[pairs[-2]['date']]) if len(pairs)>1 else None
                    else:value=None
                if dim=='inflation':threshold=rules.inflation;score=1 if round(value,10)<=threshold else -1
                elif name=='Unemployment':threshold=rules.unemployment_change;score=(1 if change is not None and round(change,10)<threshold else -1) if change is not None else None
                elif name.startswith('Payroll'):threshold=rules.payroll;score=1 if round(value,10)>=threshold else -1
                elif sid=='ICSA':threshold=rules.claims_change;score=(1 if round(change,10)<=threshold else -1) if change is not None else None
                elif dim=='growth':threshold=rules.growth;score=1 if round(value,10)>threshold else -1
                elif name.startswith('10Y-') and value is not None:threshold=rules.inversion;score=1 if round(value,10)>=threshold else -1
                if name=='Fed funds':score=0
        if value is None:score=None
        groups[dim].append(score)
        signals.append(dict(dimension=dim,series_id=sid,name=name,value=value,change=change,period=period,units=units,score=score,threshold=threshold,method=' -> '.join(ops) if not name.startswith('10Y-') else 'Same-date Treasury subtraction',source=info))
    scores={d:mean(v) if all(x is not None for x in v) else None for d,v in groups.items()}
    vals={p['date']:float(p['value']) if p['value'] is not None else None for p in unrate}
    ordered=sorted(vals);grid=[]
    if ordered:
        y,m=ordered[0].year,ordered[0].month
        while date(y,m,1)<=min(at,ordered[-1]):
            grid.append(date(y,m,1));m+=1
            if m==13:y+=1;m=1
    gaps=sahm([vals.get(d) for d in grid]);gap=gaps[-1] if gaps and (at-grid[-1]).days<=100 else None
    return dict(sample_count=sum(s['value'] is not None for s in signals),missing_ratio=sum(s['value'] is None for s in signals)/len(signals),state=classify(scores,previous),scores=scores,signals=signals,sahm=dict(source=unrate_info,missing_reason='Incomplete trailing monthly unemployment window' if gap is None else None,reference_urls=['https://fred.stlouisfed.org/series/SAHMCURRENT','https://fred.stlouisfed.org/series/SAHMREALTIME'],value=gap,period=grid[-1] if grid else None,units='Percentage points',threshold=rules.sahm,triggered=round(gap,10)>=rules.sahm if gap is not None else None,sample_count=sum(v is not None for v in gaps),history=[dict(date=d,value=v) for d,v in zip(grid,gaps)],method='Current three-month unemployment average minus minimum of preceding 12 three-month averages (current month excluded). Latest = revised UNRATE, compare SAHMCURRENT; real-time release-specific differences are disclosed.'),rules=rules.model_dump(),data_mode=mode,as_of=at if mode=='vintage' else None,evaluated_date=at,status='PARTIAL' if any(v is None for v in scores.values()) else 'AVAILABLE',note='Transparent research rule, not NBER designation or recession probability. Latest history is revised-data hindsight; vintage is date precision only.')

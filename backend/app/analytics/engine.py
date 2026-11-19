from fastapi import HTTPException
from app.workspace_engine import native_history, transform_points, align_points, period_grid, recession_intervals
from app.workspace_schemas import ChartConfiguration
from app.analytics.statistics import correlation, rolling_statistics
from datetime import date
from types import SimpleNamespace

WARNINGS=['Correlation is not causation or verified prediction.','Raw levels can be nonstationary; use defensible growth/change transforms.','Autocorrelation reduces independent information; no iid p-values are reported.','Best lag maximizes absolute in-sample correlation; multiple lag searches overfit. Compare trailing-window stability and reserve out-of-sample validation.']

def prepare(db,c):
    end=min(c.end,c.as_of if c.data_mode=='vintage' else date.today());dates=period_grid(c.start,end,c.frequency)
    if len(dates)*len(c.lines)>16000:raise HTTPException(422,'Maximum 16,000 aligned input points')
    series=[];native_cache={}
    for line in c.lines:
        key=(line.series_id,c.data_mode,c.as_of)
        if key not in native_cache:native_cache[key]=native_history(db,*key)
        spec,points,info=native_cache[key];units=None;aligned=[];native_points=points;converted_points=[]
        if line.subtract_series_id:raise HTTPException(422,'Select stored spread series or use the recession spread panel; analytics lines do not accept expressions')
        if spec:
            try:
                converted,points=transform_points(spec,points,line.calculations);units=converted.units;converted_points=points
                aligned=align_points(points,'daily' if spec.frequency=='weekly' and c.frequency in ('monthly','quarterly') else spec.frequency,c.frequency,line.alignment,c.start,end)
            except ValueError as e:raise HTTPException(422,str(e)) from None
        if c.data_fingerprints.get(line.key) and c.data_fingerprints[line.key]!=info.get('dependency_fingerprint'):info={**info,'saved_version_warning':'Source differs from saved fingerprint'}
        from app.availability import availability
        state=availability(native_points,converted_points,aligned,source_status=info['status'],has_history=bool(native_points))
        series.append(dict(key=line.key,name=line.display_name,series_id=line.series_id,units=units,provenance=info,availability=state,values=[p['value'] for p in aligned] if aligned else [None]*len(dates)))
    rec=[]
    if c.show_ex_post_recessions:
        rec,_=recession_intervals(db,SimpleNamespace(show_recessions=True,data_mode='latest',start=c.start),end)
    return dict(configuration=c.model_dump(mode='json'),dates=dates,alignment_note='Native transforms first; weekly-to-month/quarter assigns each published weekly observation to its observation-date bucket, no prorating or forward fill',series=series,recessions=rec,recession_note='Ex-post USREC chronology only; never an input to calculations or historical decisions.',warnings=WARNINGS,precision='Date-level ALFRED only; latest history uses revised values',effective_end=end)

def analyze(db,c,operation):
    data=prepare(db,c);s=data['series'];dates=data['dates'];x,y=s[0]['values'],s[1]['values']
    if operation=='correlation':
        data['matrix']=[dict(x=a['key'],y=b['key'],**correlation(a['values'],b['values'],dates,c.method,c.min_samples)) for a in s for b in s]
    elif operation=='rolling-correlation':
        data['rolling']=[dict(date=d,**correlation(x[max(0,i-c.window+1):i+1],y[max(0,i-c.window+1):i+1],dates[max(0,i-c.window+1):i+1],c.method,max(c.min_samples,c.window))) for i,d in enumerate(dates)]
    elif operation=='lead-lag':
        lags=[]
        for k in range(-c.max_lag,c.max_lag+1):
            indices=[i for i in range(len(dates)) if 0<=i+k<len(dates)]
            result=correlation([x[i] for i in indices],[y[i+k] for i in indices],[dates[i] for i in indices],c.method,c.min_samples)
            recent=indices[-c.window:]
            result['trailing_stability']=correlation([x[i] for i in recent],[y[i+k] for i in recent],[dates[i] for i in recent],c.method,c.min_samples)
            lags.append(dict(lag=k,**result))
        valid=[p for p in lags if p['value'] is not None]
        data.update(lags=lags,best_lag=max(valid,key=lambda p:abs(p['value']))['lag'] if valid else None,lag_definition='Corr(X_t,Y_(t+k)); k>0: X leads Y. k<0: X lags Y. Retrospective sample association, not forecast accuracy.')
        data['stability']=[]
        if valid:
            k=data['best_lag']
            for stop in range(c.window-1,len(dates)):
                start=stop-c.window+1;indices=[i for i in range(start,stop+1) if start<=i+k<=stop]
                data['stability'].append(dict(date=dates[stop],lag=k,**correlation([x[i] for i in indices],[y[i+k] for i in indices],[dates[i] for i in indices],c.method,c.min_samples)))
        data['stability_note']='Trailing windows at the retrospectively selected full-sample lag; not an out-of-sample forecasting test.'
    else:data['statistics']=[dict(key=a['key'],points=rolling_statistics(a['values'],dates,c.window)) for a in s]
    data['autocorrelation']=[dict(key=a['key'],lag1=correlation(a['values'][:-1],a['values'][1:],dates[1:],'pearson',c.min_samples)) for a in s]
    return data

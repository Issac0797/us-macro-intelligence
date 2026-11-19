"""Official live source checks and independently calculated research assertions."""
import json,math,hashlib,statistics
from datetime import date
from pathlib import Path
from sqlalchemy import text,select
from app.db import SessionLocal
from app.models import Observation
from app.providers import FredAPIProvider
from app.alfred import AlfredProvider
from app.config import get_settings
from app.analytics.schemas import AnalyticsConfiguration
from app.analytics.engine import analyze
from app.analytics.cycle import current,Thresholds
from app.analytics.statistics import sahm
from app.workspace_engine import native_history
from app.sync import latest_observations
from app.treasury import spread_history

def validate_lags(data):
 x,y=[s['values'] for s in data['series']]
 for point in data['lags']:
  k=point['lag'];pairs=[(x[i],y[i+k]) for i in range(len(x)) if 0<=i+k<len(y) and x[i] is not None and y[i+k] is not None]
  if point['value'] is not None:assert abs(point['value']-statistics.correlation([p[0] for p in pairs],[p[1] for p in pairs]))<1e-10

def main():
 import os
 os.chdir(Path(__file__).resolve().parents[1])
 p=FredAPIProvider(get_settings());a=AlfredProvider(get_settings());report={'status':'PASS','checks':[]}
 try:
  with SessionLocal() as db:
   for sid in ('ICSA','SAHMCURRENT','SAHMREALTIME'):
    ref=p.observations(sid,date(2025,1,1),date.today());stored={r.observation_date:r.value for r in db.scalars(latest_observations(db,sid))}
    assert all(stored.get(r.observation_date)==r.value for r in ref);report['checks'].append({'source':sid,'official_matches':len(ref)})
   c=AnalyticsConfiguration.model_validate(dict(start='2010-01-01',end=str(date.today()),lines=[dict(key='u',series_id='UNRATE',display_name='Unrate',calculations=[dict(transform='absolute_change')]),dict(key='p',series_id='PAYEMS',display_name='Payroll',calculations=[dict(transform='absolute_change')])]))
   r=analyze(db,c,'rolling-correlation');n=0
   for i,point in enumerate(r['rolling']):
    x=r['series'][0]['values'][max(0,i-23):i+1];y=r['series'][1]['values'][max(0,i-23):i+1]
    if len(x)==24 and all(v is not None for v in x+y) and len(set(x))>1 and len(set(y))>1:
     assert abs(point['value']-statistics.correlation(x,y))<1e-10;n+=1
   report['checks'].append({'rolling_UNRATE_PAYEMS_independent_matches':n})
   c.lines[1].series_id='UNRATE';c.lines[0].series_id='PCEPILFE';c.lines[0].calculations[0].transform='yoy';lead=analyze(db,c,'lead-lag');validate_lags(lead);report['checks'].append({'core_pce_lags':len(lead['lags']),'best_in_sample_only':lead['best_lag']})
   spread=spread_history(db,date(2020,1,1),date.today());assert all(p['value']==float(p['left_value']-p['right_value']) or abs(p['value']-(p['left_value']-p['right_value']))<1e-10 for s in spread['spreads'] for p in s['points'] if p['value'] is not None)
   report['checks'].append({'inversion_runs':{s['name']:len(s['inversion_intervals']) for s in spread['spreads']}})
   u=native_history(db,'UNRATE','latest',None)[1];g=sahm([float(r['value']) if r['value'] is not None else None for r in u]);ref={r.observation_date:float(r.value) for r in db.scalars(latest_observations(db,'SAHMCURRENT')) if r.value is not None};samples=[(g[i],ref[r['date']]) for i,r in enumerate(u) if r['date']>=date(2020,1,1) and r['date'] in ref and g[i] is not None];assert all(abs(x-y)<.011 for x,y in samples)
   report['checks'].append({'Sahm_current_applicable_samples':len(samples),'rounding_tolerance_pp':.011,'missing_windows':'Excluded, not filled'})
   realtime={r.observation_date:float(r.value) for r in db.scalars(latest_observations(db,'SAHMREALTIME')) if r.value is not None};matches=[]
   for at in (date(2020,6,15),date(2023,6,15),date(2024,6,15)):
    result=current(db,'vintage',at,Thresholds());assert result['state']=='Insufficient Data'
    assert all(s['period'] is None or s['period']<=at for s in result['signals'])
    rows=a.snapshot('UNRATE',at,start=date(at.year-2,1,1));gaps=sahm([float(r.value) if r.value is not None else None for r in rows]);v=gaps[-1];period=rows[-1].observation_date
    matches.append({'as_of':str(at),'period':str(period),'computed':v,'official_realtime':realtime.get(period),'difference_pp':v-realtime[period] if v is not None and period in realtime else None})
   assert all(m['difference_pp'] is not None and abs(m['difference_pp'])<.011 for m in matches)
   report['real_time_sahm_checks']=matches
   c=AnalyticsConfiguration.model_validate(dict(start='2020-01-01',end='2023-06-15',data_mode='vintage',as_of='2023-06-15',lines=[dict(key='p',series_id='PAYEMS',display_name='Payroll'),dict(key='u',series_id='UNRATE',display_name='Unrate')]))
   old=analyze(db,c,'correlation');c.show_ex_post_recessions=True;shade=analyze(db,c,'correlation');assert old['matrix']==shade['matrix'] and old['recessions']==[] and len(shade['recessions'])>0
   c.data_mode='latest';c.as_of=None;latest=analyze(db,c,'correlation');assert old['series'][0]['values']!=latest['series'][0]['values']
   report['checks'].append({'vintage_differs_from_latest':True,'expost_isolated':True,'future_versions':0,'GDP_INDPRO_growth':[(s['name'],s['value']) for s in current(db,'latest',date.today(),Thresholds())['signals'] if s['dimension']=='growth']})
   baseline=json.loads(Path('../.local/iteration5-baseline.json').read_text());integrity={}
   for name in ('release_events','series_vintages','vintage_observations','vintage_metadata'):
    rows=db.execute(text(f'SELECT * FROM {name} ORDER BY 1,2')).all();integrity[name]=hashlib.sha256(repr(rows).encode()).hexdigest()==baseline[name]['sha256']
   rows=db.execute(select(Observation.__table__).where(Observation.series_id.in_(baseline['series_ids'])).order_by(Observation.id,Observation.series_id)).all();integrity['original_observations']=hashlib.sha256(repr(rows).encode()).hexdigest()==baseline['observations']['sha256'];assert all(integrity.values()),integrity
   report['integrity']=integrity;report['counts']=[dict(r) for r in db.execute(text("SELECT series_id,count(*) AS observations FROM observations WHERE series_id in ('ICSA','SAHMCURRENT','SAHMREALTIME') GROUP BY series_id")).mappings()];report['total_observations']=db.scalar(text('SELECT count(*) FROM observations'))
   Path('../.local/iteration5-live-verification.json').write_text(json.dumps(report,default=str,indent=2));print(json.dumps(report,default=str,indent=2))
 finally:p.close();a.close()
if __name__=='__main__':main()

"""Actual FRED/ALFRED -> PostgreSQL -> Next proxy validation. No fixture imports."""
import hashlib
import json
import math
from datetime import date
from pathlib import Path
import httpx
from sqlalchemy import text, select, func
from app.config import get_settings
from app.providers import FredAPIProvider, parse_observations
from app.alfred import AlfredProvider
from app.db import SessionLocal
from app.models import Observation
from app.workspace_schemas import ChartConfiguration
from app.treasury import MATURITIES


def main():
    fred=FredAPIProvider(get_settings());alfred=AlfredProvider(get_settings())
    report={'status':'PASS','checks':[]}
    try:
        with httpx.Client(base_url='http://127.0.0.1:3000',trust_env=False,timeout=90) as web,SessionLocal() as db:
            def chart(lines,**kw):
                cfg=ChartConfiguration.model_validate({**dict(start='2020-01-01',end=str(date.today()),frequency='monthly',lines=lines),**kw})
                response=web.post('/api/v1/workspace/chart-data',json=cfg.model_dump(mode='json'));response.raise_for_status();return response.json()
            params=dict(series_id='PCEPILFE',observation_start='2018-01-01',observation_end=str(date.today()),realtime_start=str(date.today()),realtime_end=str(date.today()),limit=100000)
            raw=parse_observations(fred.json('series/observations',{**params,'units':'lin'}))
            by_month={(r.observation_date.year,r.observation_date.month):float(r.value) for r in raw if r.value is not None}
            n=0
            for transform,official in [('mom','pch'),('yoy','pc1'),('annualized_3m',None),('annualized_6m',None)]:
                result=chart([dict(key='pce',series_id='PCEPILFE',display_name='Core PCE',calculations=[dict(transform=transform)])])
                expected={}
                if official:
                    expected={(r.observation_date.year,r.observation_date.month):float(r.value) for r in parse_observations(fred.json('series/observations',{**params,'units':official})) if r.value is not None}
                else:
                    lag,exponent=(3,4) if transform=='annualized_3m' else (6,2)
                    for (y,m),value in by_month.items():
                        month=y*12+m-1-lag;before=by_month.get((month//12,month%12+1))
                        if before:expected[y,m]=((value/before)**exponent-1)*100
                for point in result['series'][0]['points']:
                    d=date.fromisoformat(point['date']);reference=expected.get((d.year,d.month))
                    if point['value'] is not None and reference is not None:
                        assert math.isclose(point['value'],reference,abs_tol=2e-5),(transform,point['date'])
                        n+=1
                report['checks'].append({'name':'Core PCE '+transform,'source':'FRED official units '+official if official else 'Independent formula on official raw observations','result':'PASS'})
            report['core_pce_values_checked']=n
            labor=chart([dict(key='p',series_id='PAYEMS',display_name='Payroll',alignment='period_average'),dict(key='u',series_id='UNRATE',display_name='Unrate',alignment='period_average',axis='right')],data_mode='vintage',as_of='2023-06-15',frequency='quarterly')
            checked=0
            for output in labor['series']:
                reference=alfred.snapshot(output['series_id'],date(2023,6,15),start=date(2019,1,1))
                quarters={}
                for r in reference:
                    if r.value is not None and r.observation_date<=date(2023,6,15):quarters.setdefault((r.observation_date.year,(r.observation_date.month-1)//3),[]).append(float(r.value))
                for point in output['points']:
                    d=date.fromisoformat(point['date']);assert d<=date(2023,6,15)
                    if point['effective_vintage']:assert point['effective_vintage']<='2023-06-15'
                    values=quarters.get((d.year,(d.month-1)//3))
                    if point['value'] is not None:
                        assert math.isclose(point['value'],sum(values)/len(values),abs_tol=1e-8);checked+=1
            report['checks'].append({'name':'PAYEMS / UNRATE quarterly average at common ALFRED as_of','matched':checked,'future_values':0,'result':'PASS'})
            missing=chart([dict(key='d',series_id='DGS2',display_name='Treasury')],data_mode='vintage',as_of='2023-06-15')
            assert missing['series'][0]['provenance']['status']=='HISTORICAL_VINTAGE_UNAVAILABLE' and missing['series'][0]['points']==[]
            spread=web.get('/api/v1/yield-curve/spreads',params={'start':'2023-01-01','end':'2023-12-31'});spread.raise_for_status()
            official=fred.observations('T10Y2Y',date(2023,1,1),date(2023,12,31));values={str(r.observation_date):float(r.value) for r in official if r.value is not None}
            checked=0
            for point in spread.json()['spreads'][0]['points']:
                if point['value'] is not None and point['date'] in values:
                    assert math.isclose(point['value'],values[point['date']],abs_tol=1e-8);checked+=1
            report['checks'].append({'name':'Same-date DGS10 − DGS2 vs official T10Y2Y','matched':checked,'result':'PASS'})
            dates=['2020-01-02','2023-06-15','2024-09-16']
            response=web.get('/api/v1/yield-curve',params=[('include_latest','false')]+[('dates',d) for d in dates]);response.raise_for_status()
            matched=0
            for curve in response.json()['curves']:
                day=date.fromisoformat(curve['used_date'])
                for point in curve['points']:
                    values=fred.observations(point['series_id'],day,day)
                    expected=float(values[0].value) if values and values[0].value is not None else None
                    assert point['value']==expected,(point['series_id'],day);matched+=1
            report['checks'].append({'name':'Three historical curves vs official FRED snapshots','dates':dates,'maturities_checked':matched,'result':'PASS'})
            baseline=json.loads(Path('../.local/iteration4-baseline.json').read_text())
            integrity={}
            for name in ('release_events','series_vintages','vintage_observations','vintage_metadata'):
                rows=db.execute(text(f'SELECT * FROM {name} ORDER BY 1,2')).all()
                assert len(rows)==baseline[name]['count'] and hashlib.sha256(repr(rows).encode()).hexdigest()==baseline[name]['sha256'],name
                integrity[name]='unchanged full checksum'
            original_ids=[s['id'] for s in baseline['series']]
            rows=db.execute(select(Observation.__table__).where(Observation.series_id.in_(original_ids)).order_by(Observation.id,Observation.series_id)).all()
            assert len(rows)==baseline['observations']['count'] and hashlib.sha256(repr(rows).encode()).hexdigest()==baseline['observations']['sha256']
            integrity['original_observations']='unchanged full checksum'
            counts=[dict(r) for r in db.execute(text("SELECT series_id,count(*) AS observations,count(value) AS nonnull,min(observation_date) AS first_date,max(observation_date) AS last_date FROM observations GROUP BY series_id ORDER BY series_id")).mappings()]
            report.update(integrity=integrity,series_counts=counts,total_observations=db.scalar(text('SELECT count(*) FROM observations')))
            for route in ('/','/inflation','/labor','/growth','/monetary','/calendar','/historical-snapshot','/revisions','/workspace','/yield-curve'):
                assert web.get(route).status_code==200,route
            report['page_http']='10 routes: 200'
            Path('../.local/iteration4-live-verification.json').write_text(json.dumps(report,default=str,indent=2),encoding='utf-8')
            print(json.dumps(report,default=str,indent=2))
    finally:fred.close();alfred.close()


if __name__=='__main__':main()

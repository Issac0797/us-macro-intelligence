from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
import math
import pytest
from pydantic import ValidationError
from sqlalchemy import select, func
from app.workspace_schemas import ChartConfiguration, Calculation
from app.workspace_engine import transform_points, align_points, chart_data
from app.workspace_models import ChartWorkspace
from app.treasury import seed_treasury, yield_curves, spread_history, curve_changes
from app.models import Observation
from app.providers import Datum
from app.sync import sync_series
from test_sync import FakeProvider
from test_vintages import ArchiveFixture, END, datum
from app.vintage_sync import sync_archive


def config(**overrides):
    data=dict(title='Test research',start='2020-01-01',end='2020-06-30',frequency='monthly',show_recessions=False,
        lines=[dict(key='a',series_id='CPIAUCSL',display_name='CPI',calculations=[dict(transform='raw')])])
    data.update(overrides)
    return ChartConfiguration.model_validate(data)


def seed(db,sid,values):
    provider=FakeProvider();provider.rows=[Datum(date.fromisoformat(d),Decimal(str(v)) if v is not None else None,str(v) if v is not None else '.') for d,v in values]
    sync_series(db,provider,sid)


def native(values,frequency='monthly'):
    spec=SimpleNamespace(frequency=frequency,unit_kind='index',units='Index',seasonal_adjustment='SA')
    points=[dict(date=date(2020,i+1,1),value=Decimal(str(v)) if v is not None else None,raw_value=str(v),version=str(i),vintage_date=None,source='test',collected_at=None,released_at=None,realtime_start=None,realtime_end=None) for i,v in enumerate(values)]
    return spec,points


def test_z_score_backward_population_and_zero_variance():
    spec,rows=native([1,2,3,999]);_,result=transform_points(spec,rows,[Calculation(transform='z_score',window=3)])
    assert result[0]['value'] is None
    assert float(result[2]['value'])==pytest.approx(math.sqrt(1.5))
    _,constant=transform_points(*native([2,2,2]),[Calculation(transform='z_score',window=3)])
    assert constant[-1]['value'] is None


def test_index_explicit_nonzero_base_and_no_future_base_leak():
    _,rows=transform_points(*native([100,200,300]),[Calculation(transform='index_100',base_date=date(2020,2,1))])
    assert [p['value'] for p in rows]==[None,100,150]
    for base in (date(1999,1,1),date(2020,1,1)):
        with pytest.raises(ValueError):transform_points(*native([0,1,2]),[Calculation(transform='index_100',base_date=base)])


def test_payroll_change_then_three_observation_average():
    spec,rows=native([100,103,109,118]);spec.unit_kind='level'
    _,out=transform_points(spec,rows,[Calculation(transform='absolute_change'),Calculation(transform='moving_average',window=3)])
    assert out[-1]['value']==6 and out[-2]['value'] is None


def test_growth_rules_and_missing_not_zero():
    _,rows=transform_points(*native([100,None,121]),[Calculation(transform='mom')])
    assert all(p['value'] is None for p in rows)
    spec,rows=native([1,2,3]);spec.unit_kind='rate'
    with pytest.raises(ValueError):transform_points(spec,rows,[Calculation(transform='annualized_3m')])
    with pytest.raises(ValueError):transform_points(spec,rows,[Calculation(transform='index_100',base_date=date(2020,1,1))])


@pytest.mark.parametrize('method,expected',[('period_end',None),('period_average',2),('last_available',3)])
def test_alignment_methods_are_distinct_and_no_cross_bucket_fill(method,expected):
    _,rows=native([1,3,None]);rows[0]['date']=date(2020,1,2);rows[1]['date']=date(2020,1,30);rows[2]['date']=date(2020,1,31)
    result=align_points(rows,'daily','monthly',method,date(2020,1,1),date(2020,2,29))
    assert result[0]['value']==expected and result[1]['value'] is None
    assert result[0]['missing_count']==1 and result[1]['source_count']==0


def test_closed_periods_weekly_and_upsample_protection():
    _,rows=native([2]);rows[0]['date']=date(2020,1,3)
    assert align_points(rows,'daily','weekly','period_end',date(2020,1,1),date(2020,1,4))==[]
    assert align_points(rows,'daily','weekly','period_end',date(2020,1,1),date(2020,1,5))[0]['date']==date(2020,1,5)
    with pytest.raises(ValueError):align_points(rows,'quarterly','monthly','period_end',date(2020,1,1),date(2020,6,1))


def test_multi_series_dual_axes_and_search(client,db):
    seed(db,'CPIAUCSL',[('2020-01-01',100),('2020-02-01',102)])
    seed(db,'UNRATE',[('2020-01-01',4),('2020-02-01',4.1)])
    cfg=config();cfg.lines.append(cfg.lines[0].model_copy(update=dict(key='b',series_id='UNRATE',display_name='Unemployment',axis='right')))
    response=client.post('/api/v1/workspace/chart-data',json=cfg.model_dump(mode='json'))
    assert response.status_code==200,response.text
    data=response.json();assert len(data['series'])==2 and set(data['axes'])=={'left','right'}
    cfg.lines[1].axis='left'
    assert client.post('/api/v1/workspace/chart-data',json=cfg.model_dump(mode='json')).status_code==422
    search=client.get('/api/v1/workspace/series/search?q=CPI&category=inflation').json()
    assert all(s['id'] in ('CPIAUCSL','CPILFESL') for s in search['series'])
    assert client.get('/api/v1/workspace/series/search?q=NEVEREXISTS').json()['count']==0


def test_monthly_labor_to_quarterly_same_frequency(db):
    seed(db,'PAYEMS',[('2020-01-01',100),('2020-02-01',103),('2020-03-01',109)])
    seed(db,'UNRATE',[('2020-01-01',4),('2020-02-01',5),('2020-03-01',6)])
    cfg=config(frequency='quarterly',lines=[dict(key='pay',series_id='PAYEMS',display_name='Payroll',axis='left',alignment='period_average'),dict(key='u',series_id='UNRATE',display_name='Unrate',axis='right',alignment='period_average')])
    data=chart_data(db,cfg);assert data['series'][0]['points'][0]['value']==104
    assert data['series'][1]['points'][0]['value']==5 and data['dates'][0]==date(2020,3,31)


def test_vintage_no_future_values_in_rolling_or_alignment_and_no_fallback(client,db):
    sync_archive(db,ArchiveFixture(),'CPIAUCSL',end=END)
    cfg=config(data_mode='vintage',as_of='2020-03-15',end='2020-06-30',lines=[dict(key='a',series_id='CPIAUCSL',display_name='CPI'),dict(key='b',series_id='DGS2',display_name='Treasury',axis='right')])
    data=chart_data(db,cfg)
    assert all(d<=date(2020,3,15) for d in data['dates'])
    a=data['series'][0];assert a['points'][0]['value']==100
    assert all(p['effective_vintage'] is None or p['effective_vintage']<=date(2020,3,15) for p in a['points'])
    assert data['series'][1]['provenance']['status']=='HISTORICAL_VINTAGE_UNAVAILABLE' and data['series'][1]['points']==[]
    cfg.lines=cfg.lines[:1];cfg.lines[0].calculations=[Calculation(transform='z_score',window=3)]
    assert all(p['value'] is None for p in chart_data(db,cfg)['series'][0]['points'])
    raw=cfg.model_dump(mode='json');raw['as_of']='2020-03-15T00:00:00Z'
    assert client.post('/api/v1/workspace/chart-data',json=raw).status_code==422


def test_vintage_rolling_zscore_excludes_later_revision_with_complete_window(db):
    provider=ArchiveFixture()
    provider.rows=[datum('2019-12-01','2020-01-01',str(END),'90'),
        datum('2020-01-01','2020-02-01','2020-03-31','100'),
        datum('2020-01-01','2020-04-01',str(END),'999'),
        datum('2020-02-01','2020-03-01',str(END),'110')]
    provider.vintage_dates=lambda *a,**k:[date(2020,m,1) for m in (1,2,3,4)]
    sync_archive(db,provider,'CPIAUCSL',end=END)
    cfg=config(start='2019-12-01',data_mode='vintage',as_of='2020-03-15',
        lines=[dict(key='z',series_id='CPIAUCSL',display_name='Rolling Z',calculations=[dict(transform='z_score',window=3)])])
    before=chart_data(db,cfg)['series'][0]['points'][-1]
    assert before['date']==date(2020,2,29) and before['value']==pytest.approx(math.sqrt(1.5))
    cfg.as_of=date(2020,4,15)
    after=next(p for p in chart_data(db,cfg)['series'][0]['points'] if p['date']==date(2020,2,29))
    assert after['value']!=pytest.approx(before['value'])


def test_workspace_crud_duplicate_rename_and_version(client,db):
    payload=dict(name='Original',description='Local',configuration=config().model_dump(mode='json'))
    saved=client.post('/api/v1/workspaces',json=payload);assert saved.status_code==201
    identifier=saved.json()['id']
    assert client.get('/api/v1/workspaces/'+identifier).json()['configuration']==payload['configuration']
    payload['name']='Renamed';assert client.put('/api/v1/workspaces/'+identifier,json=payload).json()['name']=='Renamed'
    duplicate=client.post('/api/v1/workspaces',json=payload).json()['id'];assert duplicate!=identifier
    assert client.get('/api/v1/workspaces').json()['count']==2
    payload['configuration']['configuration_version']=2
    assert client.post('/api/v1/workspaces',json=payload).status_code==422
    row=db.get(ChartWorkspace,duplicate);row.configuration_version=2;db.commit()
    assert client.get('/api/v1/workspaces/'+duplicate).status_code==409
    assert client.delete('/api/v1/workspaces/'+identifier).status_code==200
    assert client.get('/api/v1/workspaces/'+identifier).status_code==404


def test_limits_and_schema_validation(client):
    raw=config().model_dump(mode='json')
    for changed in ({'lines':[]},{'lines':raw['lines']*7},{'configuration_version':2},{'start':'2022-01-01','end':'2020-01-01'},{'data_mode':'vintage','as_of':None}):
        assert client.post('/api/v1/workspace/chart-data',json={**raw,**changed}).status_code==422
    with pytest.raises(ValidationError):Calculation(transform='moving_average',window=4)
    with pytest.raises(ValidationError):Calculation(transform='index_100')


def test_source_fingerprint_change_warning(db):
    seed(db,'CPIAUCSL',[('2020-01-01',100)])
    cfg=config();cfg.data_fingerprints={'a':'old'}
    assert 'differ' in chart_data(db,cfg)['warnings'][0]


def test_treasury_same_date_spreads_missing_holiday_and_changes(client,db):
    seed_treasury(db)
    seed(db,'DGS2',[('2020-01-02',1),('2020-01-03',None),('2020-01-06',2)])
    seed(db,'DGS10',[('2020-01-02',2),('2020-01-03',3),('2020-01-06',1)])
    exact=yield_curves(db,[date(2020,1,4)],False)['curves'][0]
    assert exact['available_maturities']==0 and len(exact['points'])==11 and exact['used_date'] is None
    near=yield_curves(db,[date(2020,1,4)],False,True)['curves'][0]
    assert near['used_date']==date(2020,1,3) and next(p for p in near['points'] if p['series_id']=='DGS2')['value'] is None
    spread=spread_history(db,date(2020,1,1),date(2020,1,7))['spreads'][0]
    assert [p['value'] for p in spread['points']]==[1,None,-1]
    assert spread['sample_count']==2 and spread['percentile']==50 and len(spread['inversion_intervals'])==1
    changes=curve_changes(db,date(2020,1,2),date(2020,1,6))['changes']
    assert next(p for p in changes if p['series_id']=='DGS2')['change_bp']==100
    assert client.get('/api/v1/yield-curve?dates=2020-01-02&dates=2020-01-03&dates=2020-01-06').status_code==200
    assert client.get('/api/v1/yield-curve?'+ '&'.join(['dates=2020-01-02']*4)).status_code==422
    assert client.get('/api/v1/yield-curve/changes?start=2020-01-02&end=2020-01-06').status_code==200


def test_workspace_spread_is_native_same_date_expression(db):
    seed(db,'DGS2',[('2020-01-02',1),('2020-01-03',None)])
    seed(db,'DGS10',[('2020-01-02',2),('2020-01-03',3)])
    cfg=config(frequency='daily',end='2020-01-03',lines=[dict(key='s',series_id='DGS10',subtract_series_id='DGS2',display_name='Spread')])
    points=chart_data(db,cfg)['series'][0]['points']
    assert points[1]['value']==1 and points[2]['value'] is None

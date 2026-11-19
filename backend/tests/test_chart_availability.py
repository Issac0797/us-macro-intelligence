from datetime import date
from app.workspace_engine import chart_data
from test_workspace import config, seed


def test_observation_empty_reasons_are_distinct(client, db):
    path='/api/v1/series/CPIAUCSL/observations'
    assert client.get(path).json()['availability']['status']=='NEEDS_SYNC'
    seed(db,'CPIAUCSL',[('2020-01-01',100),('2020-02-01',101)])
    assert client.get(path).json()['availability']['status']=='AVAILABLE'
    assert client.get(path+'?start=2021-01-01').json()['availability']['status']=='NO_OBSERVATIONS_IN_RANGE'
    assert client.get(path+'?transform=yoy').json()['availability']['status']=='INSUFFICIENT_TRANSFORM_DATA'
    assert client.get(path+'?start=2021-01-01&end=2020-01-01').status_code==422


def test_workspace_no_sync_range_transform_and_closed_periods(db):
    assert chart_data(db,config())['series'][0]['availability']['status']=='NEEDS_SYNC'
    seed(db,'CPIAUCSL',[('2020-01-01',100),('2020-02-01',101)])
    def state(**kw):return chart_data(db,config(**kw))['series'][0]['availability']['status']
    assert state()=='AVAILABLE'
    assert state(start='2021-01-01',end='2021-06-30')=='NO_OBSERVATIONS_IN_RANGE'
    assert state(end='2020-01-15')=='NO_CLOSED_PERIODS'
    assert state(lines=[dict(key='a',series_id='CPIAUCSL',display_name='CPI',calculations=[dict(transform='yoy')])])=='INSUFFICIENT_TRANSFORM_DATA'
    seed(db,'CPIAUCSL',[('2020-01-01',None),('2020-02-01',None)])
    assert state()=='SOURCE_VALUES_MISSING'


def test_vintage_never_reuses_latest_and_real_zero_is_available(db):
    seed(db,'UNRATE',[('2020-01-01',0)])
    cfg=config(lines=[dict(key='u',series_id='UNRATE',display_name='Unemployment')])
    assert chart_data(db,cfg)['series'][0]['availability']['status']=='AVAILABLE'
    cfg.data_mode='vintage';cfg.as_of=date(2020,6,30)
    line=chart_data(db,cfg)['series'][0]
    assert line['availability']['status']=='HISTORICAL_VINTAGE_UNAVAILABLE'
    assert not line['points']
    assert 'no latest-data fallback' in line['provenance']['message']

import pytest
from datetime import date
from app.dashboard_schemas import DashboardConfiguration
from test_workspace import seed
from test_vintages import ArchiveFixture,END
from app.vintage_sync import sync_archive


def configuration():
    return dict(kind='dashboard',configuration_version=2,title='Research',start='2020-01-01',end='2020-12-31',active_chart_id='stable-chart-a',charts=[dict(id='stable-chart-a',configuration=dict(lines=[dict(key='line-a',series_id='CPIAUCSL',display_name='CPI')],start='2020-01-01',end='2020-12-31'))])


def test_dashboard_roundtrip_and_v1_compatibility(client):
    config=configuration();created=client.post('/api/v1/workspaces',json={'name':'Dashboard QA','configuration':config})
    assert created.status_code==201,created.text
    row=created.json();assert row['configuration_version']==2
    loaded=client.get('/api/v1/workspaces/'+row['id']).json();assert loaded['configuration']==row['configuration']
    old=client.post('/api/v1/workspaces',json={'name':'Old chart','configuration':config['charts'][0]['configuration']});assert old.status_code==201 and old.json()['configuration_version']==1
    assert client.put('/api/v1/workspaces/'+row['id'],json={'name':'Renamed','configuration':config}).status_code==200
    assert client.delete('/api/v1/workspaces/'+row['id']).status_code==200


@pytest.mark.parametrize('mutation',[lambda c:c['charts'].append(c['charts'][0]),lambda c:c.update(active_chart_id='absent'),lambda c:c['charts'][0].update(grid=dict(x=11,w=6)),lambda c:c.update(data_mode='vintage',as_of='2023-06-15'),lambda c:c.update(charts=c['charts']*9)])
def test_dashboard_rejects_ambiguous_ids_context_and_unbounded_layout(mutation):
    config=configuration();mutation(config)
    with pytest.raises(ValueError):DashboardConfiguration.model_validate(config)


def test_observation_details_native_missing_and_parameter_validation(client,db):
    seed(db,'CPIAUCSL',[('2020-01-01',100)])
    r=client.get('/api/v1/workspace/observation-details?series_id=CPIAUCSL&observation_date=2020-01-01');assert r.status_code==200,r.text
    data=r.json();assert data['observation_date']=='2020-01-01' and data['source_url'].startswith('https://fred.stlouisfed.org/')
    assert data['related_events']==[] and data['source_release_date'] is None
    missing=client.get('/api/v1/workspace/observation-details?series_id=CPIAUCSL&observation_date=1900-01-01').json();assert missing['value'] is None and missing['status']=='NO_OBSERVATION'
    for query in ['series_id=BAD%3C&observation_date=2020-01-01','series_id=CPIAUCSL&observation_date=2020-01-01T12:00:00','series_id=CPIAUCSL&observation_date=2020-01-01&data_mode=vintage']:
        assert client.get('/api/v1/workspace/observation-details?'+query).status_code==422


def test_point_vintage_cutoff_never_substitutes_latest(client,db):
    sync_archive(db,ArchiveFixture(),'CPIAUCSL',end=END)
    query='/api/v1/workspace/observation-details?series_id=CPIAUCSL&observation_date=2020-01-01&data_mode=vintage&as_of='
    old=client.get(query+'2020-02-15').json();late=client.get(query+'2020-04-15').json()
    assert old['value']==100 and late['value']==102
    assert old['vintage_date']<='2020-02-15'
    missing=client.get(query+'1900-01-01').json();assert missing['value'] is None and not missing['historical_available']
    unknown=client.get(query.replace('CPIAUCSL','DFF')+'2020-02-15').json();assert unknown['value'] is None and unknown['status']=='HISTORICAL_VINTAGE_UNAVAILABLE'

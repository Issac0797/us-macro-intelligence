import pytest,math
from datetime import date
from app.analytics.statistics import correlation,ranks,rolling_statistics,sahm
from app.analytics.cycle import classify,Thresholds,current
from app.analytics.schemas import AnalyticsConfiguration
from app.analytics.engine import analyze
from test_workspace import seed
from test_vintages import ArchiveFixture,END
from app.vintage_sync import sync_archive

def cfg(**kw):return AnalyticsConfiguration.model_validate(dict(start='2020-01-01',end='2020-05-01',min_samples=3,window=3,lines=[dict(key='x',series_id='CPIAUCSL',display_name='X'),dict(key='y',series_id='PAYEMS',display_name='Y')],**kw))
@pytest.mark.parametrize('method',['pearson','spearman'])
def test_correlations(method):
 r=correlation([1,2,3,None],[2,4,6,7],list(range(4)),method,3);assert r['value']==pytest.approx(1) and r['sample_count']==3 and r['missing_ratio']==.25
 assert correlation([1,1,1],[1,2,3],[1,2,3],method,3)['value'] is None
 assert correlation([1],[2],[1],method,3)['status']=='INSUFFICIENT_DATA'
def test_rank_ties():assert ranks([3,1,1,2])==[4,1.5,1.5,3]
def test_rolling_no_future():
 a=rolling_statistics([1,2,3,999],list(range(4)),3);assert a[2]['z_score']==pytest.approx(math.sqrt(1.5));assert a[2]['percentile']==100;assert a[0]['mean'] is None
 assert rolling_statistics([1,None,2],[1,2,3],3)[-1]['mean'] is None
def test_sahm_previous_window():
 x=[4]*14+[5];assert sahm(x)[-1]==pytest.approx(1/3)
 assert sahm([4]*10+[None]+[4]*5)[-1] is None
@pytest.mark.parametrize('scores,previous,expected',[
 ({'inflation':1,'labor':1,'growth':1,'financial':1},None,'Expansion'),
 ({'inflation':-1,'labor':1,'growth':1,'financial':1},None,'Slowdown'),
 ({'inflation':1,'labor':-1,'growth':-1,'financial':1},None,'Contraction'),
 ({'inflation':1,'labor':1,'growth':1,'financial':1},'Contraction','Recovery'),
 ({'inflation':1,'labor':0,'growth':0,'financial':1},None,'Slowdown'),
 ({'inflation':1,'labor':None,'growth':1,'financial':1},None,'Insufficient Data')])
def test_regime(scores,previous,expected):assert classify(scores,previous)==expected

def test_api_config_and_vintage_no_fallback(client,db):
 sync_archive(db,ArchiveFixture(),'CPIAUCSL',end=END)
 c=cfg(data_mode='vintage',as_of='2020-03-15');r=client.post('/api/v1/analytics/correlation',json=c.model_dump(mode='json'));assert r.status_code==200,r.text
 data=r.json();assert all(d<='2020-03-15' for d in data['dates']);assert all(v is None for v in data['series'][1]['values']);assert data['recessions']==[]
 for path in ('rolling-correlation','lead-lag','rolling-statistics'):assert client.post('/api/v1/analytics/'+path,json=c.model_dump(mode='json')).status_code==200
 save=client.post('/api/v1/workspaces',json={'name':'Research','configuration':c.model_dump(mode='json')});assert save.status_code==201,save.text
 assert client.get('/api/v1/workspaces/'+save.json()['id']).json()['configuration']['kind']=='analytics'
 bad=c.model_dump(mode='json');bad['window']=0;assert client.post('/api/v1/analytics/correlation',json=bad).status_code==422
 assert client.get('/api/v1/business-cycle/current?data_mode=vintage').status_code==422
 assert client.get('/api/v1/analytics/metadata').status_code==200

def test_lag_direction_and_rolling(db):
 xs=[3,1,7,2,9,5,4,8,0,6,2,5];ys=[None]+xs[:-1]
 seed(db,'CPIAUCSL',[(f'2020-{i+1:02d}-01',v) for i,v in enumerate(xs)]);seed(db,'PAYEMS',[(f'2020-{i+1:02d}-01',v) for i,v in enumerate(ys)])
 c=cfg();c.end=date(2020,12,31);r=analyze(db,c,'lead-lag');assert r['best_lag']==1
 c.lines=list(reversed(c.lines));assert analyze(db,c,'lead-lag')['best_lag']==-1
 r=analyze(db,c,'rolling-correlation');assert r['rolling'][0]['value'] is None
 assert any('nonstationary' in x for x in r['warnings'])

def test_cycle_missing_is_insufficient_and_no_expost(db):
 r=current(db,'vintage',date(2020,3,1),Thresholds());assert r['state']=='Insufficient Data';assert r['sahm']['value'] is None


def test_weekly_native_calendar_lags():
 from app.transforms import calculate,Transform
 from app.providers import Datum
 from types import SimpleNamespace
 from decimal import Decimal
 from datetime import timedelta
 spec=SimpleNamespace(frequency='weekly',unit_kind='level',seasonal_adjustment='SA',units='Number')
 rows=[SimpleNamespace(observation_date=date(2020,1,4)+timedelta(days=7*i),value=Decimal(i+1),raw_value=str(i+1),version='test',source='fixture',collected_at=None,released_at=None,realtime_start=None,realtime_end=None) for i in range(3)]
 assert calculate(spec,rows,Transform.ABSOLUTE_CHANGE)[-1]['value']==1
 assert calculate(spec,rows,Transform.MOVING_AVERAGE,3)[-1]['value']==2


def test_cycle_spread_change_uses_both_legs(db):
 seed(db,'DGS2',[('2020-01-02',1),('2020-01-03',1.8)])
 seed(db,'DGS10',[('2020-01-02',2),('2020-01-03',3)])
 result=current(db,'latest',date(2020,1,4),Thresholds())
 spread=next(s for s in result['signals'] if s['name']=='10Y-2Y')
 assert spread['value']==pytest.approx(1.2) and spread['change']==pytest.approx(.2)
 seed(db,'UNRATE',[('2020-01-02',3.2),('2020-01-03',3.5)])
 rate=next(s for s in current(db,'latest',date(2020,1,4),Thresholds())['signals'] if s['name']=='Unemployment')
 assert rate['change']==.3 and rate['score']==-1

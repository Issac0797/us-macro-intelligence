from datetime import date,timedelta
from decimal import Decimal
import httpx,pytest
from sqlalchemy import select,func
from app.alfred import AlfredProvider
from app.providers import ProviderError,parse_observations
from app.config import Settings
from app.vintage_sync import sync_archive
from app.vintage_models import VintageObservation,SeriesVintage,VintageSyncJob,VintageArchive
from app.vintage_queries import snapshot,revision_data,revision_amount,summary_statistics
from app.transforms import Transform
from app.legacy_checks import fed_document_time

END=date(2020,5,1)
def datum(period,start,end,value):return dict(date=period,realtime_start=start,realtime_end=end,value=value)

class ArchiveFixture:
    def __init__(self):
        self.calls=[];self.fail=False
        self.rows=[datum('2019-01-01','2019-02-01','2020-03-31','100'),datum('2019-01-01','2020-04-01',str(END),'999'),
          datum('2020-01-01','2020-02-01','2020-03-31','100'),datum('2020-01-01','2020-04-01',str(END),'102'),datum('2020-02-01','2020-03-01',str(END),'200')]
    def vintage_dates(self,*args,**kwargs):return [date(2019,2,1),date(2020,2,1),date(2020,3,1),date(2020,4,1)]
    def metadata_history(self,*args):return [dict(realtime_start='2019-02-01',realtime_end=str(END),units='Index 2017=100',frequency_short='M',seasonal_adjustment_short='SA')]
    def interval_page(self,sid,end,offset):
        self.calls.append(offset)
        if offset==2 and self.fail:raise ProviderError('Fixture temporary failure')
        rows=self.rows[offset:offset+2]
        return {'count':len(self.rows),'observations':rows},parse_observations({'observations':rows})

def test_alfred_native_parsing_and_vintage_pagination():
    calls=[]
    def handler(request):
        calls.append(request)
        if 'vintagedates' in request.url.path:
            offset=int(request.url.params['offset']);return httpx.Response(200,json={'count':2,'vintage_dates':['2020-02-01' if offset==0 else '2020-04-01']})
        return httpx.Response(200,json={'count':1,'observations':[datum('2020-01-01','2020-02-01','2020-02-01','.') ]})
    p=AlfredProvider(Settings(_env_file=None,fred_api_key='test-key'),client=httpx.Client(transport=httpx.MockTransport(handler)),sleep=lambda _:None)
    assert p.vintage_dates('PAYEMS',end=END)==[date(2020,2,1),date(2020,4,1)]
    rows=p.snapshot('PAYEMS',date(2020,2,1));assert rows[0].value is None
    assert calls[-1].url.params['realtime_start']=='2020-02-01' and calls[-1].url.params['realtime_end']=='2020-02-01'

def test_invalid_catalog_never_accepted():
    p=AlfredProvider(Settings(_env_file=None,fred_api_key='test-key'),client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'count':1,'vintage_dates':['2025-01-01']}))),sleep=lambda _:None)
    with pytest.raises(ProviderError):p.vintage_dates('PAYEMS',end=END)

def test_vintage_idempotence_and_no_current_overwrite(db):
    from app.models import Observation
    initial=db.scalar(select(func.count()).select_from(Observation));provider=ArchiveFixture()
    sync_archive(db,provider,'CPIAUCSL',end=END);sync_archive(db,provider,'CPIAUCSL',end=END)
    assert provider.calls==[0,2,4]
    assert db.scalar(select(func.count()).select_from(VintageObservation))==5
    assert db.scalar(select(func.count()).select_from(SeriesVintage))==4
    assert db.scalar(select(func.count()).select_from(Observation))==initial
    sync_archive(db,provider,'CPIAUCSL',end=END,force=True)
    assert db.scalar(select(func.count()).select_from(VintageObservation))==5

def test_resume_page_checkpoint_and_atomic_visibility(db):
    provider=ArchiveFixture();provider.fail=True
    with pytest.raises(ProviderError):sync_archive(db,provider,'CPIAUCSL',end=END)
    job=db.scalar(select(VintageSyncJob));assert job.status=='failed' and job.checkpoint==2
    assert db.scalar(select(func.count()).select_from(VintageObservation))==0
    provider.fail=False;provider.calls=[];sync_archive(db,provider,'CPIAUCSL',end=END)
    assert provider.calls==[2,4] and job.attempts==2 and job.status=='complete'

def test_future_values_never_enter_snapshot_or_transform(db):
    sync_archive(db,ArchiveFixture(),'CPIAUCSL',end=END)
    result=snapshot(db,'CPIAUCSL',date(2020,3,15),Transform.YOY)
    point=next(p for p in result['observations'] if p['date']==date(2020,1,1))
    assert point['value']==0
    assert all(p['vintage_date']<=date(2020,3,15) and p['date']<=date(2020,3,15) for p in result['observations'])
    old=snapshot(db,'CPIAUCSL',date(2020,2,15));assert all(p['date']!=date(2020,2,1) for p in old['observations'])
    assert next(p for p in old['observations'] if p['date']==date(2020,1,1))['value']==100

def test_missing_history_no_latest_fallback(db):
    assert snapshot(db,'PAYEMS',date(2020,1,1))['coverage']=='NOT_AVAILABLE'
    sync_archive(db,ArchiveFixture(),'CPIAUCSL',end=END)
    for d in (date(1900,1,1),date(2021,1,1)):
        r=snapshot(db,'CPIAUCSL',d);assert r['coverage']=='NOT_AVAILABLE' and r['observations']==[]

@pytest.mark.parametrize('initial,revised,kind,expected',[(100,105,'level',(5,5)),(-100,-90,'level',(10,10)),(0,10,'level',(10,None)),(4,4.2,'rate',(pytest.approx(.2),None)),(None,2,'level',(None,None))])
def test_revision_math(initial,revised,kind,expected):
    a=Decimal(str(initial)) if initial is not None else None;b=Decimal(str(revised))
    assert revision_amount(a,b,kind)==expected

def test_unit_rebase_is_not_economic_revision(db):
    provider=ArchiveFixture()
    provider.metadata_history=lambda *a:[dict(realtime_start='2019-02-01',realtime_end='2020-03-31',units='Index 2000=100',frequency_short='M',seasonal_adjustment_short='SA'),dict(realtime_start='2020-04-01',realtime_end=str(END),units='Index 2017=100',frequency_short='M',seasonal_adjustment_short='SA')]
    sync_archive(db,provider,'CPIAUCSL',end=END)
    _,_,rows=revision_data(db,'CPIAUCSL');r=next(r for r in rows if r['observation_date']==date(2020,1,1))
    assert r['absolute_revision'] is None and not r['comparable']
    assert not snapshot(db,'CPIAUCSL',date(2020,3,15))['latest_comparable']

def test_revision_summary_windows_and_censoring(db):
    sync_archive(db,ArchiveFixture(),'CPIAUCSL',end=END)
    _,_,rows=revision_data(db,'CPIAUCSL',date(2020,1,1),date(2020,1,1))
    assert rows[0]['initial_value']==100 and rows[0]['revised_value']==102 and rows[0]['absolute_revision']==2
    assert rows[0]['timeline'][1]['step_revision']==2
    stats=summary_statistics(rows);assert stats['sample_count']==1 and stats['by_units'][0]['mean_revision']==2
    _,_,fixed=revision_data(db,'CPIAUCSL',date(2020,1,1),date(2020,1,1),30)
    assert fixed[0]['absolute_revision']==0
    _,_,censored=revision_data(db,'CPIAUCSL',date(2020,1,1),date(2020,1,1),180)
    assert censored[0]['censored'] and summary_statistics(censored)['sample_count']==0

def test_overlap_rejected_and_old_archive_preserved(db):
    p=ArchiveFixture();sync_archive(db,p,'CPIAUCSL',end=END)
    p.rows[0]['realtime_end']='2020-04-02'
    with pytest.raises(ProviderError):sync_archive(db,p,'CPIAUCSL',end=END,force=True)
    assert snapshot(db,'CPIAUCSL',date(2020,3,15))['coverage']=='AVAILABLE'
    assert db.scalar(select(func.count()).select_from(VintageObservation))==5

def test_vintage_api_and_date_precision(client,db):
    sync_archive(db,ArchiveFixture(),'CPIAUCSL',end=END)
    assert client.get('/api/v1/vintages/CPIAUCSL?page_size=2').json()['count']==4
    a=client.get('/api/v1/historical-snapshot?series_id=CPIAUCSL&as_of=2020-03-15').json()
    assert a['precision']=='date' and 'intraday' in a['precision_note']
    from datetime import datetime
    assert datetime.fromisoformat(a['retrieved_at']).utcoffset()==timedelta(0)
    assert client.get('/api/v1/vintages/CPIAUCSL/observations?vintage_date=2020-03-15').status_code==200
    assert client.get('/api/v1/revisions/CPIAUCSL?observation_date=2020-01-01').json()['observations'][0]['absolute_revision']==2
    assert client.get('/api/v1/revisions/CPIAUCSL/summary?start=2020-01-01&end=2020-01-01').json()['sample_count']==1
    assert client.get('/api/v1/vintage-sync/status').json()['observation_interval_count']==5
    for query in ('as_of=2020-03-15T08:00:00Z','as_of=2020-03-15T00:00:00Z','as_of=2020-03-15&page_size=1001','as_of=2020-03-15&frequency=quarterly','as_of=2020-03-15&transform=invalid','as_of=2020-03-15&start=2020-02-01&end=2020-01-01'):
        r=client.get('/api/v1/historical-snapshot?series_id=CPIAUCSL&'+query);assert r.status_code==422 and 'error' in r.json()
    assert client.get('/api/v1/vintages/CPIAUCSL/observations').status_code==422
    assert client.get('/api/v1/revisions/CPIAUCSL/summary?window_days=31').status_code==422
    assert client.get('/api/v1/revisions/CPIAUCSL/summary?window_days=90').status_code==200
    assert client.get('/api/v1/revisions/CPIAUCSL?window_days=30').status_code==200
    compared=client.get('/api/v1/historical-snapshot?series_id=CPIAUCSL&as_of=2020-04-15&compare_as_of=2020-03-15').json()
    assert compared['latest_as_of']=='2020-03-15'
    p=next(p for p in compared['observations'] if p['date']=='2020-01-01')
    assert p['value']==102 and p['latest_value']==100 and p['difference']==-2
    bounded=client.get('/api/v1/revisions/CPIAUCSL?observation_date=2020-01-01&as_of=2020-03-15').json()['observations'][0]
    assert bounded['revised_value']==100 and all(t['vintage_date']<='2020-03-15' for t in bounded['timeline'])

def test_fed_time_only_from_explicit_official_document():
    text='<p class="article__time">October 28, 2026</p><p>For release at 2:00 p.m. EDT</p>'
    assert fed_document_time(text).hour==18
    assert fed_document_time(text.replace('EDT','EST')) is None
    assert fed_document_time('<p>FOMC meeting October 28, 2026</p>') is None

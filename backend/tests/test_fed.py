"""Official HTML fixture tests plus isolated storage/API/PIT regression."""
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import httpx,pytest
from sqlalchemy import select,func
from bs4 import BeautifulSoup
from app.fed import parsers,queries
from app.fed.models import Meeting,Document,Decision,Projection,Dot,DocumentVersion
from app.fed.sync import ingest_document,sync_fed
from app.fed.provider import FedProvider
from app.providers import ProviderError
FIX=Path(__file__).parent/'fixtures/fed'
def fixture(name):return (FIX/name).read_text(encoding='utf-8')
def add_meeting(db,mid='2026-10-28'):
 m=Meeting(id=mid,start_date=date.fromisoformat(mid)-timedelta(days=1),end_date=date.fromisoformat(mid),source_url=parsers.CALENDAR);db.add(m);db.commit();return m
class Provider:
 attempts=1
 def __init__(self,html):self.html=html
 def fetch(self,url):return self.html

def test_official_calendar_discovery_cross_month_and_notation():
 rows=parsers.calendar(fixture('calendar.html'));assert len(rows)==24
 assert '2025-08-22' not in [r['id'] for r in rows]
 m=next(r for r in rows if r['id']=='2024-05-01');assert m['start_date']==date(2024,4,30)
 assert all(not d['url'].endswith('.pdf') for r in rows for d in r['documents'])
 assert next(r for r in rows if r['id']=='2026-12-09')['documents']==[]

def test_statement_exact_range_votes_and_time():
 p=parsers.parse(fixture('2026-10-28-statement.html'),'statement');assert p['content']['lower']=='3.75';assert p['content']['upper']=='4'
 assert (p['content']['vote_for'],p['content']['vote_against'])==(10,2)
 assert 'Lisa D. Cook and Beth M. Hammack' in p['content']['dissent']
 assert p['published_at']==datetime(2026,10,28,18,tzinfo=timezone.utc)

def test_statement_multiple_dissent_reasons_not_one_vote():
 p=parsers.parse(fixture('2026-04-29-statement.html'),'statement')['content'];assert p['vote_for']==8;assert p['vote_against']==4
 assert 'easing bias' in p['dissent']

def test_september_statement_raise_and_mixed_fractions():
 p=parsers.parse(fixture('2026-09-16-statement.html'),'statement')['content'];assert p['lower']=='3.75';assert p['upper']=='4';assert p['vote_for']==12
 assert parsers.rate('3-3/4')==Decimal('3.75');assert parsers.rate('1/4')==Decimal('.25')

def test_effective_date_is_not_decision_date():
 p=parsers.parse(fixture('2026-10-28-implementation.html'),'implementation');assert p['content']['effective_date']=='2026-10-29'

def test_sep_headers_medians_missing_and_dot_counts():
 p=parsers.parse(fixture('2026-09-16-sep.html'),'sep');rows=p['projections'];dots=p['dots']
 assert next(r for r in rows if r['variable']=='gdp' and r['target_year']=='2026' and r['statistic']=='median' and not r['is_previous'])['value']==Decimal('2.3')
 assert next(r for r in rows if r['variable']=='core_pce' and r['target_year']=='Longer run' and r['statistic']=='median' and not r['is_previous'])['value'] is None
 assert all(d['rate']>0 and d['participants']>0 for d in dots)
 assert {y:sum(d['participants'] for d in dots if d['target_year']==y) for y in {d['target_year'] for d in dots}}=={'2026':18,'2027':18,'2028':17,'2029':17,'Longer run':18}

def test_timezone_conflict_downgrades_without_inventing_hour():
 p=parsers.parse('<p>For release at 2:00 p.m., EDT, December 18, 2024</p>','minutes');assert p['precision']=='DATE';assert 'review required' in p['publication_evidence']

def test_unknown_or_changed_layout_fails_closed():
 with pytest.raises(ValueError):parsers.parse('<html>No article</html>','statement')
 with pytest.raises(ValueError):parsers.sep(BeautifulSoup('<table></table>','html.parser'))
 assert parsers.parse('<html>Unknown time</html>','conference')['precision']=='UNKNOWN'

def test_provider_retry_and_no_access_bypass():
 calls=[]
 def handler(req):
  calls.append(req);return httpx.Response(503 if len(calls)<2 else 200,headers={'content-type':'text/html'},text='<html>ok</html>')
 p=FedProvider(httpx.Client(transport=httpx.MockTransport(handler)),sleep=lambda _:None);assert p.fetch(parsers.CALENDAR)=='<html>ok</html>';assert len(calls)==2
 with pytest.raises(ProviderError):p.fetch('https://example.org')
 p.close()

def test_provider_403_is_blocked_without_retry():
 calls=[]
 def handler(req):calls.append(req);return httpx.Response(403)
 p=FedProvider(httpx.Client(transport=httpx.MockTransport(handler)),sleep=lambda _:None)
 with pytest.raises(ProviderError):p.fetch(parsers.CALENDAR)
 assert len(calls)==1;p.close()

def test_idempotent_sync_evidence_and_recovery(db):
 m=add_meeting(db);spec={'url':'https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm','kind':'statement'}
 class Broken:
  attempts=1
  def fetch(self,url):raise ProviderError('blocked')
 assert ingest_document(db,Broken(),m,spec).status=='BLOCKED'
 p=Provider(fixture('2026-10-28-statement.html'));d=ingest_document(db,p,m,spec,True);assert d.status=='VERIFIED'
 ingest_document(db,p,m,spec,True)
 assert db.scalar(select(func.count()).select_from(Document))==1
 assert db.scalar(select(func.count()).select_from(Decision))==1
 assert db.scalar(select(func.count()).select_from(DocumentVersion))==1
 p.html=p.html.replace('Inflation remains elevated.','Inflation remains elevated. ');ingest_document(db,p,m,spec,True)
 assert db.scalar(select(func.count()).select_from(DocumentVersion))==2

def test_sep_idempotence_and_exact_year_alignment(db):
 m=add_meeting(db,'2026-09-16');spec={'url':'https://www.federalreserve.gov/monetarypolicy/fomcprojtabl20260916.htm','kind':'sep'};p=Provider(fixture('2026-09-16-sep.html'))
 ingest_document(db,p,m,spec,True);n=db.scalar(select(func.count()).select_from(Projection));ingest_document(db,p,m,spec,True)
 assert db.scalar(select(func.count()).select_from(Projection))==n
 # Matching variable with a different target year must remain missing.
 old=add_meeting(db,'2026-06-17');od=Document(meeting_id=old.id,kind='sep',source_url='https://www.federalreserve.gov/test',status='VERIFIED');db.add(od);db.flush()
 db.add(Projection(document_id=od.id,meeting_id=old.id,variable='gdp',target_year='2025',statistic='median',is_previous=False,value=9,raw_value='9'));db.commit()
 r=queries.projections(db,m.id,old.id);assert all(r['previous_release_value'] is None for r in r['aligned'])

def test_predecision_and_minutes_have_no_future_leak(db):
 m=add_meeting(db,'2026-09-16');docs=[Document(meeting_id=m.id,kind='statement',source_url='https://www.federalreserve.gov/s',status='VERIFIED',precision='MINUTE',published_at=datetime(2026,9,16,18,tzinfo=timezone.utc)),Document(meeting_id=m.id,kind='minutes',source_url='https://www.federalreserve.gov/m',status='VERIFIED',precision='DATE',published_at=datetime(2026,10,7,4,tzinfo=timezone.utc)),Document(meeting_id=m.id,kind='conference',source_url='https://www.federalreserve.gov/u',status='PARTIAL',precision='UNKNOWN')]
 db.add_all(docs);db.commit()
 pre=queries.historical(db,m.id);assert pre['as_of']==date(2026,9,15);assert not pre['documents'];assert pre['precision']=='DATE_LEVEL_ONLY'
 assert all(not s['points'] for s in pre['macro'])
 post=queries.historical(db,m.id,'post');assert [d['kind'] for d in post['documents']]==['statement']
 late=queries.historical(db,m.id,'post',date(2026,10,7));assert {d['kind'] for d in late['documents']}=={'statement','minutes'}
 with pytest.raises(__import__('fastapi').HTTPException):queries.historical(db,m.id,'pre',date(2026,9,16))

def test_date_precision_not_intraday():
 d=Document(status='VERIFIED',precision='DATE',published_at=datetime(2026,9,16,4,tzinfo=timezone.utc))
 assert not queries.visible(d,datetime(2026,9,16,18,tzinfo=timezone.utc))
 assert queries.visible(d,datetime(2026,9,17,4,tzinfo=timezone.utc))
 d.precision='MINUTE';assert not queries.visible(d,d.published_at)

def test_diff_preserves_both_originals_and_explains_tags(db):
 for mid in ['2026-09-16','2026-10-28']:
  m=add_meeting(db,mid);ingest_document(db,Provider(fixture(mid+'-statement.html')),m,{'kind':'statement','url':f'https://www.federalreserve.gov/{mid}'},True)
 r=queries.compare(db,'2026-09-16','2026-10-28');assert any(c['kind']=='modified' for c in r['changes']);assert any(c['kind']=='added' and 'Voting against' in ' '.join(c['after']) for c in r['changes'])
 assert [p for c in r['changes'] for p in c['before']]==r['left']['content']['paragraphs']
 assert [p for c in r['changes'] for p in c['after']]==r['right']['content']['paragraphs']
 assert any(c['topics'].get('Policy Decision') for c in r['changes'])

def test_api_validation_and_missing_no_fake_fill(client):
 for path in ['meetings?year=2023','meetings?page_size=1000','rates?start=2026-01-02&end=2026-01-01','rates?start=1900-01-01&end=2026-01-01','historical-snapshot?meeting_id=2026-09-16&mode=bad','historical-snapshot?meeting_id=2026-99-99']:
  r=client.get('/api/v1/fed/'+path);assert r.status_code==422,r.text;assert 'error' in r.json()
 assert client.get('/api/v1/fed/meetings/2026-09-16').status_code==404
 r=client.get('/api/v1/fed/projections');assert r.status_code==200;assert not r.json()['items']
 assert client.get('/api/v1/fed/sync/status').json()['natural_release_validation']=='PENDING_REAL_RELEASE_VALIDATION'

def test_rates_and_change_statistics_from_official_decisions(db,client):
 m=add_meeting(db);ingest_document(db,Provider(fixture('2026-10-28-statement.html')),m,{'kind':'statement','url':'https://www.federalreserve.gov/s'},True)
 d=db.get(Decision,m.id);d.change_bp=Decimal('25');db.commit()
 r=client.get('/api/v1/fed/rate-decisions').json();assert r['statistics']['hiking']==1;assert r['sample_count']==1
 assert client.get('/api/v1/fed/overview').json()['recent']['decision']['upper']==4

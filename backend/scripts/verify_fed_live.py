"""Live official-vs-storage validation. Never log authenticated request URLs."""
import hashlib,json,re,logging
from collections import defaultdict
from datetime import date
from pathlib import Path
from decimal import Decimal
from bs4 import BeautifulSoup
from sqlalchemy import select,text,func
from app.db import SessionLocal
from app.config import get_settings
from app.providers import FredAPIProvider
from app.fed.provider import FedProvider
from app.fed.models import Meeting,Document,Decision,Projection,Dot
from app.fed import queries

logging.getLogger('httpx').setLevel(logging.WARNING)
report={'checked_on':date.today().isoformat(),'checks':[]};out=Path('../.local')
def check(name,source,scope,matches,mismatches,reasons=None):
 report['checks'].append(dict(name=name,source_url=source,scope=scope,matches=matches,mismatches=mismatches,reasons=reasons or [],status='PASS' if not mismatches else 'PARTIAL'))
provider=FedProvider();fred=FredAPIProvider(get_settings())
try:
 with SessionLocal() as db:
  cal=BeautifulSoup(provider.fetch('https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'),'html.parser');expected=[]
  for panel in cal.select('.panel'):
   if not re.search(r'202[56] FOMC Meetings',panel.get_text()[:100]):continue
   for row in panel.select('.fomc-meeting'):
    if 'notation vote' in row.get_text().lower():continue
    a=row.select_one('a[href*="/pressreleases/monetary"][href$="a.htm"]')
    if a:
     suffix=re.search(r'monetary(\d{8})a',a['href'])[1];expected.append(date(int(suffix[:4]),int(suffix[4:6]),int(suffix[6:])).isoformat())
    elif 'December' in row.get_text() and '2026' in panel.get_text()[:80]:expected.append('2026-12-09')
  found=[m.id for m in db.scalars(select(Meeting).where(Meeting.id>='2025-01-01'))]
  check('2025–2026 calendar decision/end dates','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm','all sixteen scheduled policy meetings',len(set(expected)&set(found)),len(set(expected)^set(found)))
  for mid in ['2026-09-16','2026-10-28']:
   d=db.scalar(select(Document).where(Document.meeting_id==mid,Document.kind=='statement'));s=BeautifulSoup(provider.fetch(d.source_url),'html.parser');paras=[p.get_text(' ',strip=True) for p in s.select('#article p') if p.get_text(' ',strip=True)];paras=[p for p in paras if not p.startswith(('For release at','For media inquiries','Implementation Note')) and p!='Share'];a=d.content['paragraphs'];check('Statement exact paragraphs',d.source_url,mid,len([1 for x,y in zip(paras,a) if x==y]),sum(x!=y for x,y in zip(paras,a))+abs(len(paras)-len(a)))
  diff=queries.compare(db,'2026-09-16','2026-10-28');check('Adjacent statement diff reconstruction',diff['right']['source_url'],'September → October 2026',2,int([p for c in diff['changes'] for p in c['before']]!=diff['left']['content']['paragraphs'])+int([p for c in diff['changes'] for p in c['after']]!=diff['right']['content']['paragraphs']))
  for mid in ['2026-03-18','2026-06-17','2026-09-16']:
   d=db.scalar(select(Document).where(Document.meeting_id==mid,Document.kind=='sep'));s=BeautifulSoup(provider.fetch(d.source_url),'html.parser');summary=next(t for t in s.select('table') if 'Variable' in t.get_text(' ',strip=True)[:30] and 'Central Tendency' in t.get_text(' ',strip=True)[:200]);rows=summary.select('tr');years=[t.get_text(' ',strip=True) for t in rows[1].select('th')];n=len(years)//3;matches=mismatch=0
   variables={'Change in real GDP':'gdp','Unemployment rate':'unemployment','PCE inflation':'pce','Core PCE inflation':'core_pce','Federal funds rate':'fed_funds'}
   for row in rows[2:]:
    label=row.select_one('th').get_text(' ',strip=True) if row.select_one('th') else '';var=next((v for k,v in variables.items() if label.startswith(k)),None)
    if not var:continue
    for year,cell in zip(years[:n],row.select('td')[:n]):
     raw=cell.get_text(' ',strip=True);v=Decimal(raw) if re.fullmatch(r'-?\d+(?:\.\d+)?',raw) else None
     stored=db.scalar(select(Projection).where(Projection.document_id==d.id,Projection.variable==var,Projection.target_year==year,Projection.statistic=='median',Projection.is_previous==False));ok=stored is not None and stored.value==v;matches+=ok;mismatch+=not ok
   check('SEP current medians & missing cells',d.source_url,mid,matches,mismatch)
   dt=next(t for t in s.select('table') if 'Midpoint of target range or target level' in t.get_text(' ',strip=True)[:100]);dr=dt.select('tr');years=[t.get_text(' ',strip=True) for t in dr[0].select('th')[1:]];official=defaultdict(int);matches=mismatch=0
   for row in dr[1:]:
    level=Decimal(row.select_one('th').get_text(' ',strip=True))
    for y,c in zip(years,row.select('td')):
     raw=c.get_text(' ',strip=True);count=int(raw) if raw else 0;official[y]+=count;stored=db.scalar(select(Dot).where(Dot.document_id==d.id,Dot.target_year==y,Dot.rate==level));ok=(stored.participants if stored else 0)==count;matches+=ok;mismatch+=not ok
   check('Dot frequency cells',d.source_url,{'release':mid,'participant_counts':dict(official)},matches,mismatch)
  target={}
  for sid in ['DFEDTARL','DFEDTARU']:target[sid]={r.observation_date:r.value for r in fred.observations(sid,date(2025,1,1),date.today())}
  good=bad=0;details=[]
  for d in db.scalars(select(Decision).where(Decision.meeting_id>='2025-01-01')):
   for sid,expected in [('DFEDTARL',d.lower),('DFEDTARU',d.upper)]:
    actual=target[sid].get(d.effective_date);ok=actual==expected;good+=ok;bad+=not ok
    if not ok:details.append({'decision':d.meeting_id,'effective_date':str(d.effective_date),'series':sid,'official':str(expected),'fred':str(actual)})
  check('Official decisions vs fresh FRED target bounds','https://fred.stlouisfed.org/series/DFEDTARU','2025–2026, both bounds on each documented effective date',good,bad,details)
  for mid in ['2026-03-18','2026-06-17','2026-09-16','2026-10-28']:
   pre=queries.historical(db,mid);own=[d for d in pre['documents'] if d['meeting_id']==mid];leak=[p for s in pre['macro'] for p in s['points'] if p['vintage_date']>pre['as_of'] or p['date']>pre['as_of']];post=queries.historical(db,mid,'post');minutes=[d for d in post['documents'] if d['meeting_id']==mid and d['kind']=='minutes'];check('Historical pre-decision and minutes exclusion','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm',mid,3,len(own)+len(leak)+len(minutes))
  baseline=json.loads((out/'iteration6-baseline.json').read_text());integrity={}
  for table in ['observations','release_events','series_vintages','vintage_observations','vintage_metadata']:
   if table=='observations':
    original_ids=baseline['series_ids'];rows=db.execute(text('SELECT * FROM observations WHERE series_id = ANY(:ids) ORDER BY 1,2'),{'ids':original_ids}).all()
   else:rows=db.execute(text(f'SELECT * FROM {table} ORDER BY 1,2')).all()
   h=hashlib.sha256(repr(rows).encode()).hexdigest();integrity[table]={'count':len(rows),'unchanged':h==baseline[table]['sha256']}
  report['baseline_integrity']=integrity
  report['counts']={t.__tablename__:db.scalar(select(func.count()).select_from(t)) for t in [Meeting,Document,Decision,Projection,Dot]}
  report['observations_total']=db.scalar(text('select count(*) from observations'))
  report['status']='PASS' if all(c['status']=='PASS' for c in report['checks']) and all(x['unchanged'] for x in integrity.values()) else 'PARTIAL'
  (out/'iteration6-live-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
finally:provider.close();fred.close()

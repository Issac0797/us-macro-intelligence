"""Nonblocking, auditable checks; no access-control bypass and no inferred Fed times."""
import json,re
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from sqlalchemy import select
import httpx
from app.db import SessionLocal
from app.models import utcnow
from app.release_models import ReleaseEvent,ScheduleChange

def fed_document_time(body):
    soup=BeautifulSoup(body,'html.parser');day=soup.select_one('.article__time')
    match=re.search(r'For release at (\d{1,2}:\d{2})\s+([ap])\.m\.\s+(EDT|EST)',soup.get_text(' ',strip=True))
    if not day or not match:return None
    try:
        local=datetime.strptime(day.get_text(strip=True)+' '+match[1]+' '+match[2].upper()+'M','%B %d, %Y %I:%M %p').replace(tzinfo=ZoneInfo('America/New_York'))
        if local.tzname()!=match[3]:return None
        return local.astimezone(timezone.utc)
    except ValueError:return None

def main():
    result={'bls':[],'fomc_times_confirmed':0,'real_release_validation':'PENDING_REAL_RELEASE_VALIDATION'}
    with httpx.Client(timeout=20,follow_redirects=True) as client,SessionLocal() as db:
        for url in ('https://www.bls.gov/schedule/news_release/bls.ics','https://www.bls.gov/schedule/2026/home.htm','https://www.bls.gov/feed/empsit.rss'):
            try:result['bls'].append({'url':url,'http_status':client.get(url).status_code})
            except httpx.HTTPError:result['bls'].append({'url':url,'status':'BLOCKED_NETWORK'})
        events=db.scalars(select(ReleaseEvent).where(ReleaseEvent.provider=='federal_reserve',ReleaseEvent.status=='Released',ReleaseEvent.release_name=='FOMC Statement').order_by(ReleaseEvent.scheduled_date.desc()).limit(5))
        for event in events:
            try:
                response=client.get(event.source_url);response.raise_for_status();at=fed_document_time(response.text)
                if at and event.scheduled_date==at.astimezone(ZoneInfo('America/New_York')).date():
                    old=event.scheduled_at
                    if old!=at:
                        db.add(ScheduleChange(event_id=event.id,old_snapshot=json.dumps({'scheduled_at':old.isoformat() if old else None}),new_snapshot=json.dumps({'scheduled_at':at.isoformat(),'evidence_url':event.source_url,'precision':'official_document_time'})))
                        event.scheduled_at=at;event.last_verified_at=utcnow()
                    result['fomc_times_confirmed']+=1
            except httpx.HTTPError:continue
        db.commit()
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

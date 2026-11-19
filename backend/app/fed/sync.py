"""Restartable per-document ingestion; parsed data and its raw evidence commit together."""
import hashlib,logging
from datetime import date
from decimal import Decimal
from sqlalchemy import select,delete
from app.models import utcnow,Series
from app.release_models import ReleaseEvent
from app.fed.models import Meeting,Document,DocumentVersion,Decision,Projection,Dot,SyncJob
from app.fed import parsers
from app.fed.provider import FedProvider

def aware(t):
 from datetime import timezone
 return t.replace(tzinfo=timezone.utc) if t and not t.tzinfo else t

def ingest_document(db,provider,meeting,spec,force=False):
 doc=db.scalar(select(Document).where(Document.source_url==spec['url']))
 if not doc:
  doc=Document(meeting_id=meeting.id,kind=spec['kind'],source_url=spec['url'],status='DETECTED');db.add(doc);db.commit()
 if not force and doc.retrieved_at and doc.status in ['VERIFIED','PARSED','PARTIAL'] and (utcnow()-aware(doc.retrieved_at)).total_seconds()<21600:return doc
 try:
  html=provider.fetch(doc.source_url);doc.attempts+=provider.attempts;doc.retrieved_at=utcnow();doc.status='FETCHED'
  digest=hashlib.sha256(html.encode()).hexdigest()
  if not db.scalar(select(DocumentVersion.id).where(DocumentVersion.document_id==doc.id,DocumentVersion.content_hash==digest)):
   db.add(DocumentVersion(document_id=doc.id,content_hash=digest,raw_html=html))
  doc.raw_html=html;doc.content_hash=digest
  try:
   parsed=parsers.parse(html,doc.kind,spec.get('release_date'))
  except ValueError as exc:
   doc.status='PARSE_REVIEW_REQUIRED';doc.error=str(exc);db.commit();return doc
  for field in ['published_at','precision','publication_evidence','content']:setattr(doc,field,parsed[field])
  doc.parsed_at=utcnow();doc.error=None
  doc.status='VERIFIED' if doc.precision!='UNKNOWN' and 'review required' not in (doc.publication_evidence or '') and (doc.kind!='sep' or parsed['dots']) else 'PARTIAL'
  if doc.kind=='statement':
   p=parsed['content'];decision=db.get(Decision,meeting.id)
   if not decision:decision=Decision(meeting_id=meeting.id,document_id=doc.id);db.add(decision)
   decision.lower=Decimal(p['lower']);decision.upper=Decimal(p['upper']);decision.vote_for=p['vote_for'];decision.vote_against=p['vote_against'];decision.dissent=p['dissent']
  if doc.kind=='sep':
   db.execute(delete(Projection).where(Projection.document_id==doc.id));db.execute(delete(Dot).where(Dot.document_id==doc.id))
   for row in parsed['projections']:db.add(Projection(meeting_id=meeting.id,document_id=doc.id,**row))
   for row in parsed['dots']:db.add(Dot(meeting_id=meeting.id,document_id=doc.id,**row))
  db.commit()
 except Exception as exc:
  db.rollback();doc=db.get(Document,doc.id);doc.status='BLOCKED';doc.attempts+=max(1,provider.attempts);doc.error=f'{type(exc).__name__}: official fetch or storage failed';db.commit()
  logging.warning('Fed document failed kind=%s meeting=%s',doc.kind,meeting.id)
 return doc

def sync_fed(db,provider=None,force=False):
 own=provider is None;provider=provider or FedProvider();job=SyncJob(status='DETECTED');db.add(job);db.commit()
 try:
  meetings=parsers.calendar(provider.fetch(parsers.CALENDAR));job.attempts=provider.attempts;job.status='FETCHED';db.commit()
  for entry in sorted(meetings,key=lambda m:m['id']):
   meeting=db.get(Meeting,entry['id'])
   if not meeting:meeting=Meeting(id=entry['id']);db.add(meeting)
   meeting.start_date=entry['start_date'];meeting.end_date=entry['end_date'];meeting.source_url=parsers.CALENDAR;meeting.verified_at=utcnow()
   statement=next((s['url'] for s in entry['documents'] if s['kind']=='statement'),None)
   if statement:
    event=db.scalar(select(ReleaseEvent).where(ReleaseEvent.source_url==statement))
    if event:meeting.calendar_event_id=event.id
   db.commit()
   for spec in entry['documents']:
    job.checkpoint=spec['url'];db.commit();before=db.scalar(select(Document.attempts).where(Document.source_url==spec['url'])) or 0
    doc=ingest_document(db,provider,meeting,spec,force);job.attempts+=max(0,doc.attempts-before)
    if doc.status not in ['VERIFIED','PARSED']:
     job.errors=[*job.errors,{'meeting':meeting.id,'kind':doc.kind,'status':doc.status}]
  # Recompute only official meeting decisions; never infer effective date from announcement.
  decisions=list(db.scalars(select(Decision).order_by(Decision.meeting_id)))
  previous=None
  for decision in decisions:
   decision.change_bp=(decision.upper-previous.upper)*100 if previous else None
   imp=db.scalar(select(Document).where(Document.meeting_id==decision.meeting_id,Document.kind=='implementation'))
   if imp and imp.content and imp.content.get('effective_date'):
    decision.effective_date=date.fromisoformat(imp.content['effective_date']);decision.effective_document_id=imp.id
   previous=decision
  job.status='PARTIAL' if job.errors else 'VERIFIED';job.counts={'meetings':len(meetings),'decisions':len(decisions)};job.finished_at=utcnow();db.commit()
 except Exception as exc:
  db.rollback();job.status='BLOCKED';job.errors=[{'reason':type(exc).__name__}];job.finished_at=utcnow();db.commit()
 finally:
  if own:provider.close()
 return job

def sync_rates(db):
 from app.config import get_settings
 from app.providers import FredAPIProvider
 from app.sync import insert_statement,sync_series
 p=FredAPIProvider(get_settings())
 try:
  for sid,title in [('DFEDTARL','Target lower bound'),('DFEDTARU','Target upper bound'),('EFFR','Effective federal funds rate')]:
   db.execute(insert_statement(db,Series).values(id=sid,short_name=title,title=title,category='monetary',frequency='daily',units='Percent',unit_kind='rate',seasonal_adjustment='NSA',agency='Federal Reserve',default_transform='raw',source='FRED',source_url=f'https://fred.stlouisfed.org/series/{sid}').on_conflict_do_nothing(index_elements=['id']));db.commit();sync_series(db,p,sid)
 finally:p.close()

if __name__=='__main__':
 import argparse
 from app.db import SessionLocal
 parser=argparse.ArgumentParser();parser.add_argument('--force',action='store_true');parser.add_argument('--rates',action='store_true');args=parser.parse_args()
 logging.getLogger('httpx').setLevel(logging.WARNING)
 with SessionLocal() as db:
  j=sync_fed(db,force=args.force);print(j.status,j.counts,j.errors)
  if args.rates:sync_rates(db)

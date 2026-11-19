"""Bounded policy research queries with explicit publication precision."""
import difflib,re
from datetime import date,datetime,time,timedelta,timezone
from collections import Counter,defaultdict
from fastapi import HTTPException
from sqlalchemy import select,func
from app.models import utcnow,Series,Observation
from app.sync import latest_observations
from app.fed.models import Meeting,Document,Decision,Projection,Dot,SyncJob
from app.fed.sync import aware
from app.fed.parsers import NY

DISCLAIMER='SEP reflects participants’ individual appropriate-policy assumptions; it is not a committee commitment or market probability.'
def record(row,omit=()):return {c.name:getattr(row,c.name) for c in row.__table__.columns if c.name not in omit}
def document(d,full=False):
 result=record(d,('raw_html','content','error'));result['available_content']=bool(d.content)
 if full:result['content']=d.content
 return result
def get_meeting(db,mid):
 m=db.get(Meeting,mid)
 if not m:raise HTTPException(404,'Meeting not available in supported 2024–2026 calendar')
 return m

def meetings(db,year=None,page=1,page_size=50):
 q=select(Meeting)
 if year:q=q.where(Meeting.end_date>=date(year,1,1),Meeting.end_date<=date(year,12,31))
 rows=list(db.scalars(q.order_by(Meeting.end_date.desc())));items=[]
 for m in rows[(page-1)*page_size:page*page_size]:
  r=record(m);d=db.get(Decision,m.id);r['decision']=record(d) if d else None
  docs=list(db.scalars(select(Document).where(Document.meeting_id==m.id)));r['documents']=[document(d) for d in docs];r['coverage']='SCHEDULED' if m.end_date>date.today() else 'VERIFIED' if docs and all(d.status=='VERIFIED' for d in docs) else 'PARTIAL'
  items.append(r)
 return dict(count=len(rows),page=page,page_size=page_size,items=items,source_url='https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm')
def overview(db):
 allm=meetings(db,page_size=100)['items'];today=date.today();past=[m for m in allm if m['end_date']<=today];future=sorted([m for m in allm if m['end_date']>today],key=lambda m:m['end_date'])
 latest=lambda kind:db.scalar(select(Document).where(Document.kind==kind,Document.status=='VERIFIED',Document.published_at<=utcnow()).order_by(Document.published_at.desc()).limit(1))
 last=latest('statement');sep=latest('sep');changes=list(db.scalars(select(Decision).where(Decision.change_bp!=0).order_by(Decision.meeting_id.desc()).limit(1)))
 return dict(recent=past[0] if past else None,next=future[0] if future else None,latest_statement=document(last) if last else None,latest_sep=document(sep) if sep else None,last_change=record(changes[0]) if changes else None,meetings=allm,coverage=dict(Counter(d.status for d in db.scalars(select(Document)))),natural_release_validation='PENDING_REAL_RELEASE_VALIDATION',precision_note='Unknown future publication times are not inferred.')

TOPICS={'Economic Activity':['economic activity','spending','investment','productivity'],'Labor Market':['job','employment','labor'],'Inflation':['inflation','price stability'],'Policy Decision':['target range','policy stance','federal funds'],'Balance Sheet':['securities','balance sheet','reserves','holdings']}
def paragraph_pairs(a,b):
 """Monotone dynamic alignment; similar paragraphs pair, unmatched text stays added/removed."""
 n,m=len(a),len(b);scores=[[0.]*(m+1) for _ in range(n+1)];moves={}
 for i in range(1,n+1):scores[i][0]=-.3*i;moves[i,0]='delete'
 for j in range(1,m+1):scores[0][j]=-.3*j;moves[0,j]='insert'
 for i in range(1,n+1):
  for j in range(1,m+1):
   similarity=difflib.SequenceMatcher(None,a[i-1],b[j-1],autojunk=False).ratio()
   candidates=[(scores[i-1][j]-.3,'delete'),(scores[i][j-1]-.3,'insert')]
   if similarity>=.45:candidates.append((scores[i-1][j-1]+similarity-.4,'equal' if a[i-1]==b[j-1] else 'replace'))
   scores[i][j],moves[i,j]=max(candidates,key=lambda x:x[0])
 out=[];i,j=n,m
 while i or j:
  move=moves[i,j]
  if move in ['equal','replace']:out.append((move,[a[i-1]],[b[j-1]]));i-=1;j-=1
  elif move=='delete':out.append((move,[a[i-1]],[]));i-=1
  else:out.append((move,[],[b[j-1]]));j-=1
 return list(reversed(out))

def compare(db,left,right):
 docs=[]
 for mid in [left,right]:
  d=db.scalar(select(Document).where(Document.meeting_id==mid,Document.kind=='statement',Document.status=='VERIFIED'))
  if not d or not d.content:raise HTTPException(404,'Verified statement not available')
  docs.append(d)
 a,b=[d.content['paragraphs'] for d in docs];diff=[]
 for tag,old,new in paragraph_pairs(a,b):
  tokens=[]
  aa=re.findall(r'\s+|\w+|[^\w\s]', '\n\n'.join(old));bb=re.findall(r'\s+|\w+|[^\w\s]','\n\n'.join(new))
  for tt,ii,jj,kk,ll in difflib.SequenceMatcher(None,aa,bb,autojunk=False).get_opcodes():
   if tt in ['equal','delete','replace']:tokens.append({'kind':'removed' if tt!='equal' else 'equal','text':''.join(aa[ii:jj])})
   if tt in ['insert','replace']:tokens.append({'kind':'added','text':''.join(bb[kk:ll])})
  joined=' '.join(old+new).lower();topics={topic:[word for word in words if word in joined] for topic,words in TOPICS.items()};topics={k:v for k,v in topics.items() if v}
  diff.append(dict(kind={'equal':'unchanged','replace':'modified','insert':'added','delete':'removed'}[tag],before=old,after=new,tokens=tokens,topics=topics))
 return dict(left=document(docs[0],True),right=document(docs[1],True),changes=diff,method='Monotone paragraph alignment (SequenceMatcher similarity ≥ 0.45, gap cost 0.3) then exact token diff; source paragraph text retained.',topic_note='Transparent keyword matches; research labels, not official Federal Reserve categories.',topic_rules=TOPICS)

def projections(db,mid=None,compare_to=None):
 docs=list(db.scalars(select(Document).where(Document.kind=='sep',Document.status.in_(['VERIFIED','PARTIAL'])).order_by(Document.meeting_id.desc())))
 dates=[d.meeting_id for d in docs if db.scalar(select(Projection.id).where(Projection.document_id==d.id).limit(1))]
 mid=mid or (dates[0] if dates else None)
 if not mid:return dict(meeting_id=None,available_dates=[],items=[],comparison=[],coverage='NOT_AVAILABLE',note=DISCLAIMER)
 def rows(m):return [record(p) for p in db.scalars(select(Projection).where(Projection.meeting_id==m).order_by(Projection.variable,Projection.target_year,Projection.statistic))]
 items=rows(mid)
 if not items:raise HTTPException(404,'SEP projections not available')
 other=compare_to or next((d for d in dates if d<mid),None);comparison=rows(other) if other else []
 lookup={(r['variable'],r['target_year'],r['statistic']):r for r in comparison if not r['is_previous']}
 aligned=[]
 for r in items:
  if r['is_previous']:continue
  prev=lookup.get((r['variable'],r['target_year'],r['statistic']));aligned.append({**r,'previous_release_value':prev['value'] if prev else None,'change':r['value']-prev['value'] if prev and prev['value'] is not None and r['value'] is not None else None})
 return dict(meeting_id=mid,compare_to=other,available_dates=dates,items=items,comparison=comparison,aligned=aligned,documents=[document(d) for d in docs if d.meeting_id in [mid,other]],coverage='AVAILABLE',note=DISCLAIMER,alignment='Exact variable + target year + statistic; new/missing years remain null.')

def dots(db,mid=None,compare_to=None):
 p=projections(db,mid,compare_to);selected=p['meeting_id'];items=[record(d) for d in db.scalars(select(Dot).where(Dot.meeting_id==selected).order_by(Dot.target_year,Dot.rate))] if selected else []
 counts=defaultdict(int)
 for d in items:counts[d['target_year']]+=d['participants']
 comparison=[record(d) for d in db.scalars(select(Dot).where(Dot.meeting_id==p.get('compare_to')).order_by(Dot.target_year,Dot.rate))] if p.get('compare_to') else []
 return dict(meeting_id=selected,compare_to=p.get('compare_to'),items=items,comparison=comparison,participant_counts=counts,note=DISCLAIMER,coverage='AVAILABLE' if items else 'PARSE_REVIEW_REQUIRED',source_documents=p.get('documents',[]))

def decisions(db,start,end):
 rows=list(db.scalars(select(Decision).where(Decision.meeting_id>=start.isoformat(),Decision.meeting_id<=end.isoformat()).order_by(Decision.meeting_id)))
 counts=Counter('hiking' if d.change_bp>0 else 'cutting' if d.change_bp<0 else 'holding' for d in rows if d.change_bp is not None)
 items=[]
 for d in rows:
  item=record(d);doc=db.get(Document,d.document_id);item['source_url']=doc.source_url;item['decision_date']=d.meeting_id;item['published_at']=doc.published_at;items.append(item)
 return dict(items=items,statistics=dict(counts),sample_count=len(rows),classified_count=sum(counts.values()),start=start,end=end,method='Change in official target upper bound × 100 bp versus preceding stored official meeting. First stored meeting has unknown change. Effective dates require implementation-note evidence.')

def rates(db,start,end):
 items=[]
 for sid in ['DFEDTARL','DFEDTARU','EFFR','DFF']:
  spec=db.get(Series,sid);rows=list(db.scalars(latest_observations(db,sid).where(Observation.observation_date>=start,Observation.observation_date<=end))) if spec else []
  items.append(dict(series_id=sid,source_url=spec.source_url if spec else None,points=[{'date':r.observation_date,'value':r.value} for r in rows],status='AVAILABLE' if rows else 'NOT_AVAILABLE'))
 return dict(items=items,decisions=decisions(db,start,end),units='Percent; decision changes in basis points',note='Target bounds are separate policy limits. EFFR and DFF are observed rates. Latest stored series, not historical vintages.')

def visible(d,cutoff):
 if not d.published_at or d.precision=='UNKNOWN' or d.status not in ['VERIFIED','PARTIAL']:return False
 published=aware(d.published_at)
 if d.precision=='DATE':
  day=published.astimezone(NY).date();published=datetime.combine(day+timedelta(days=1),time.min,NY).astimezone(timezone.utc)
 return published<=cutoff if d.precision=='DATE' else published<cutoff

def historical(db,mid,mode='pre',as_of=None):
 m=get_meeting(db,mid)
 day=m.end_date-timedelta(days=1) if mode=='pre' else m.end_date
 if as_of:
  if mode=='pre' and as_of>day:raise HTTPException(422,'Pre-decision cutoff must precede the decision date')
  day=as_of
 if day>date.today():raise HTTPException(422,'Historical cutoff cannot be in the future')
 cutoff=datetime.combine(day+timedelta(days=1),time.min,NY).astimezone(timezone.utc)
 all_docs=list(db.scalars(select(Document).where(Document.meeting_id<=mid).order_by(Document.meeting_id.desc(),Document.kind)))
 # Date-only documents become available after their full publication day. No guessed 14:00.
 docs=[document(d) for d in all_docs if visible(d,cutoff)]
 macro=[]
 from app.workspace_engine import native_history
 for sid in ['CPIAUCSL','CPILFESL','PCEPI','PCEPILFE','UNRATE','PAYEMS','GDPC1','ICSA','INDPRO','DGS2','DGS10','DFEDTARL','DFEDTARU','EFFR']:
  if not db.get(Series,sid):macro.append(dict(series_id=sid,status='NOT_AVAILABLE',points=[]));continue
  spec,points,info=native_history(db,sid,'vintage',day)
  macro.append(dict(series_id=sid,status=info['status'],units=spec.units if spec else None,points=points[-36:],provenance=info))
 available_statements={d['id'] for d in docs if d['kind']=='statement'};available_implementation={d['id'] for d in docs if d['kind']=='implementation'}
 ds=[]
 for d in db.scalars(select(Decision).where(Decision.meeting_id<=mid)):
  if d.document_id not in available_statements:continue
  r=record(d)
  if d.effective_document_id not in available_implementation:r['effective_date']=None;r['effective_document_id']=None
  ds.append(r)
 return dict(meeting_id=mid,mode=mode,as_of=day,cutoff_exclusive=cutoff,precision='DATE_LEVEL_ONLY',coverage='PARTIAL',documents=docs,decisions=ds,macro=macro,excluded_document_count=len(all_docs)-len(docs),notes=['Pre-decision defaults to the previous full calendar day; no intraday Point-in-Time guarantee.','Every document uses its own publication timestamp. Unknown publication is excluded.','Post review defaults to the end of decision day; later minutes require a later as_of.','No latest macro fallback. Raw official archive content retrieved now is not proof of unrecorded historical editorial revisions.'])

def status(db):
 jobs=list(db.scalars(select(SyncJob).order_by(SyncJob.id.desc()).limit(10)))
 return dict(jobs=[record(j) for j in jobs],documents=dict(Counter(d.status for d in db.scalars(select(Document)))),natural_release_validation='PENDING_REAL_RELEASE_VALIDATION',scheduled=[record(m) for m in db.scalars(select(Meeting).where(Meeting.end_date>date.today()))],refresh_seconds=21600)

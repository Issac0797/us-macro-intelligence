"""HTML adapters, independent of persistence and HTTP. Fail closed on layout changes."""
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal
from fractions import Fraction
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

BASE='https://www.federalreserve.gov'
CALENDAR=BASE+'/monetarypolicy/fomccalendars.htm'
NY=ZoneInfo('America/New_York')
def text(el):return el.get_text(' ',strip=True) if el else ''
def parse_date(s):
 try:return datetime.strptime(s,'%B %d, %Y').date()
 except ValueError:return datetime.strptime(s,'%b %d, %Y').date()
def year_label(s):return 'Longer run' if 'longer' in s.lower() else s.strip()
def decimal(s):
 s=s.strip().replace('\u2212','-')
 if not s or s in ['-','—','–','n.a.','NA']:return None
 return Decimal(s)
def rate(s):
 s=s.strip().replace('−','-')
 if '-' in s:
  whole,fraction=s.split('-',1);return Decimal(whole)+Decimal(Fraction(fraction).numerator)/Decimal(Fraction(fraction).denominator)
 f=Fraction(s);return Decimal(f.numerator)/Decimal(f.denominator)

def calendar(html):
 soup=BeautifulSoup(html,'html.parser');out=[]
 for panel in soup.select('.panel'):
  h=text(panel.select_one('.panel-heading'));m=re.search(r'(202[456]) FOMC Meetings',h)
  if not m:continue
  year=int(m[1])
  for el in panel.select('.fomc-meeting'):
   if 'notation vote' in text(el).lower():continue
   month=text(el.select_one('.fomc-meeting__month')).replace('*','').strip()
   ds=text(el.select_one('.fomc-meeting__date'));nums=re.findall(r'\d+',ds)
   if not nums:continue
   # Cross-month meetings are explicit in the calendar (e.g. Apr/May).
   months=re.split(r'[/–-]',month);end_month=months[-1].strip();start_month=months[0].strip()
   try:start=parse_date(f'{start_month} {nums[0]}, {year}');end=parse_date(f'{end_month} {nums[-1]}, {year}')
   except ValueError:continue
   docs=[]
   for a in el.select('a[href]'):
    href=urljoin(BASE,a['href']);label=text(a);kind=None
    if re.search(r'monetary\d{8}a\.htm$',href):kind='statement'
    elif label=='Implementation Note':kind='implementation'
    elif 'fomcminutes' in href and href.endswith('.htm'):kind='minutes'
    elif 'fomcprojtabl' in href and href.endswith('.htm'):kind='sep'
    elif label=='Press Conference':kind='conference'
    if kind:
     released=None
     if kind=='minutes':
      x=re.search(r'Released (\w+ \d{1,2}, \d{4})',text(el.select_one('.fomc-meeting__minutes')))
      if x:released=parse_date(x[1]).isoformat()
     docs.append(dict(kind=kind,url=href,release_date=released))
   out.append(dict(id=end.isoformat(),start_date=start,end_date=end,documents=docs))
 if not out:raise ValueError('No supported calendar layout')
 return out

def publication(soup,kind,release_date=None):
 t=text(soup);m=re.search(r'For release at (\d{1,2}:\d{2})\s*(a\.m\.|p\.m\.)[,]?\s*(EDT|EST)(?:,?\s*(\w+ \d{1,2}, \d{4}))?',t,re.I)
 dnode=soup.select_one('.article__time');d=None
 try:d=parse_date(text(dnode)) if dnode else None
 except ValueError:pass
 if m:
  if m[4]:d=parse_date(m[4])
  if d:
   hh,mm=map(int,m[1].split(':'));hh=hh%12+(12 if m[2].lower().startswith('p') else 0)
   dt=datetime.combine(d,time(hh,mm),NY)
   if dt.tzname()!=m[3].upper():
    return datetime.combine(d,time.min,NY).astimezone(timezone.utc),'DATE',m[0]+' [official timezone conflicts with calendar; date only, review required]'
   return dt.astimezone(timezone.utc),'MINUTE',m[0]
 # A calendar release date proves only day-level availability, never 14:00 by convention.
 if release_date:d=date.fromisoformat(release_date)
 if d:return datetime.combine(d,time.min,NY).astimezone(timezone.utc),'DATE',f'Official document/calendar date: {d}'
 return None,'UNKNOWN',None

def statement(soup):
 article=soup.select_one('#article')
 if not article:raise ValueError('Statement article not found')
 paragraphs=[text(p) for p in article.select('p') if text(p)]
 paragraphs=[p for p in paragraphs if not p.startswith(('For release at','For media inquiries','Implementation Note')) and p!='Share']
 joined='\n\n'.join(paragraphs)
 numeric=joined.replace('‑','-').replace('–','-')
 m=re.search(r'target range for the federal funds rate (?:by [^.]*?percentage point\s+)?(?:at|to)\s+([\d./-]+)\s+to\s+([\d./-]+)\s+percent',numeric,re.I)
 if not m:raise ValueError('Policy range requires manual review')
 if rate(m[1])>rate(m[2]):raise ValueError('Policy lower bound exceeds upper bound')
 vote=re.search(r'by a (\d+)\s*[–-]\s*(\d+) vote',joined)
 voting=re.search(r'Voting for the monetary policy action were (.*?)(?:Voting against|$)',joined,re.S)
 dissent=re.search(r'Voting against.*',joined,re.S)
 if vote:yes,no=int(vote[1]),int(vote[2])
 elif voting:
  names=re.split(r';|,|\band\b',re.sub(r',\s*(?:Chair|Vice Chair)','',voting[1]));yes=len([n for n in names if n.strip(' .\n')]);no=len(set(re.findall(r'\b[A-Z][a-z]+(?: [A-Z]\.)?(?: [A-Z][a-z]+){1,2}\b',dissent[0].split('Absent')[0]))) if dissent else 0
 else:yes=no=None
 return dict(paragraphs=paragraphs,lower=str(rate(m[1])),upper=str(rate(m[2])),vote_for=yes,vote_against=no,dissent=dissent[0] if dissent else None)

def implementation(soup):
 t=text(soup);matches=re.findall(r'Effective (\w+ \d{1,2}, \d{4}), the Federal Open Market Committee directs',t,re.I)
 return {'effective_date':parse_date(matches[0]).isoformat() if matches else None,'text':t[t.find('Decisions Regarding Monetary Policy Implementation'):t.find('Last Update:')]}

VARIABLES={'Change in real GDP':'gdp','Unemployment rate':'unemployment','PCE inflation':'pce','Core PCE inflation':'core_pce','Federal funds rate':'fed_funds'}
def sep(soup):
 tables=soup.select('table');table=next((t for t in tables if 'Central Tendency' in text(t)[:220] and 'Variable' in text(t)[:30]),None)
 if table is None:raise ValueError('SEP summary table unavailable; PARSE_REVIEW_REQUIRED')
 rows=table.select('tr');headers=rows[1].select('th');years=[year_label(text(h)) for h in headers]
 groups=rows[0].select('th')[1:];statistics=[]
 for g in groups:
  name=text(g).lower();stat='median' if 'median' in name else 'central_tendency' if 'central' in name else 'range'
  statistics.extend([stat]*int(g.get('colspan','1')))
 if len(years)!=len(statistics):raise ValueError('SEP header span mismatch')
 result=[];variable=None
 for row in rows[2:]:
  head=text(row.select_one('th'));cells=row.select('td')
  match=next((v for k,v in VARIABLES.items() if head.startswith(k)),None)
  if match:variable=match;previous=False
  elif 'projection' in head.lower() and variable:previous=True
  else:continue
  if len(cells)!=len(years):raise ValueError('SEP row width mismatch')
  for y,stat,c in zip(years,statistics,cells):
   raw=text(c).replace('\u2212','-');v=lo=hi=None
   if stat=='median':v=decimal(raw)
   elif raw and raw not in ['-','—','–']:
    nums=re.findall(r'-?\d+(?:\.\d+)?',raw.replace('–',' to '))
    if len(nums)==1:nums=nums*2
    if len(nums)!=2:raise ValueError('SEP range not understood')
    lo,hi=map(Decimal,nums)
   result.append(dict(variable=variable,target_year=y,statistic=stat,is_previous=previous,value=v,low=lo,high=hi,raw_value=raw))
 dots=[];dt=next((t for t in tables if 'Midpoint of target range or target level' in text(t)[:100]),None)
 if dt:
  dr=dt.select('tr');dy=[year_label(text(c)) for c in dr[0].select('th')[1:]]
  for row in dr[1:]:
   cells=row.select('td');r=decimal(text(row.select_one('th')))
   if r is None or len(cells)!=len(dy):raise ValueError('Dot table row mismatch')
   for y,c in zip(dy,cells):
    val=text(c)
    if not val:continue
    if not val.isdigit():raise ValueError('Non-integer dot count')
    count=int(val)
    if count:dots.append(dict(target_year=y,rate=r,participants=count))
 if not result:raise ValueError('Empty SEP')
 return result,dots

def parse(html,kind,release_date=None):
 s=BeautifulSoup(html,'html.parser');published,precision,evidence=publication(s,kind,release_date)
 content=statement(s) if kind=='statement' else implementation(s) if kind=='implementation' else {'text':text(s.select_one('#article') or s.select_one('#content') or s)[:300000]}
 projections,dots=sep(s) if kind=='sep' else ([],[])
 return dict(published_at=published,precision=precision,publication_evidence=evidence,content=content,projections=projections,dots=dots)

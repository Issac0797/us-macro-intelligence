"""Official schedules only. HTML parsers are isolated and fail closed on drift."""
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from icalendar import Calendar
from app.providers import FredTransport, ProviderError

NY = ZoneInfo('America/New_York')
UTC = timezone.utc

@dataclass
class ScheduledRelease:
    key: str
    name: str
    day: date
    at: datetime | None
    series: tuple[str, ...]
    category: str
    period: str | None = None
    url: str | None = None
    released: bool = False
    importance: str = 'high'  # Editorial classification, not an agency/market forecast.

class CalendarProvider(Protocol):
    name: str
    url: str
    def fetch(self) -> list[ScheduledRelease]: ...

def classify(title):
    t = title.lower()
    if 'consumer price index' in t: return ('CPIAUCSL','CPILFESL'), 'inflation'
    if 'personal income and outlays' in t: return ('PCEPI','PCEPILFE'), 'inflation'
    if 'employment situation' in t: return ('PAYEMS','UNRATE','CES0500000003'), 'labor'
    if 'job openings' in t: return ('JTSJOL',), 'labor'
    if 'gross domestic product' in t or re.search(r'\bGDP\b', title): return ('GDPC1',), 'growth'
    if 'retail' in t and ('sales' in t): return ('RSAFS',), 'growth'
    return (), ''

def ny_time(day, clock):
    return datetime.combine(day, datetime.strptime(clock.strip().upper(), '%I:%M %p').time(), NY).astimezone(UTC)

def parse_ics(body, source_url):
    result=[]
    try:
        cal=Calendar.from_ical(body.replace('\r\r\n','\r\n'))
        for row in cal.walk('VEVENT'):
            title=str(row.get('SUMMARY','')); series, category=classify(title)
            if not series: continue
            dt=row.decoded('DTSTART')
            if isinstance(dt,datetime):
                # Floating timestamps need an explicit source timezone.
                if dt.tzinfo is None:
                    tz=str(cal.get('X-WR-TIMEZONE',''))
                    if tz != 'America/New_York': raise ValueError('Unknown floating time zone')
                    dt=dt.replace(tzinfo=NY)
                at=dt.astimezone(UTC);day=dt.astimezone(NY).date()
            else: day,at=dt,None
            period=title.split(',',1)[1].strip() if ',' in title else None
            result.append(ScheduledRelease(str(row.get('UID') or title), title,day,at,series,category,period,source_url))
    except Exception:
        raise ProviderError('Calendar ICS schema changed or invalid time zone') from None
    if not result: raise ProviderError('Calendar contained no supported releases')
    return result

def parse_bea(body, url):
    soup=BeautifulSoup(body,'html.parser'); table=soup.select_one('#release-schedule-table')
    if not table: raise ProviderError('BEA schedule table missing')
    year=re.search(r'\b20\d{2}\b',table.select_one('thead').get_text())
    if not year: raise ProviderError('BEA schedule year missing')
    result=[]
    for row in table.select('tbody tr'):
        title=row.select_one('.release-title'); day=row.select_one('.release-date'); clock=row.select_one('small')
        if not title: raise ProviderError('BEA title column changed')
        title=title.get_text(' ',strip=True); series,category=classify(title)
        if not series: continue
        if not day: raise ProviderError('BEA release date missing')
        d=datetime.strptime(day.get_text(strip=True)+' '+year.group(),'%B %d %Y').date()
        at=ny_time(d,clock.get_text(strip=True)) if clock and re.fullmatch(r'\d{1,2}:\d{2} [AP]M',clock.get_text(strip=True)) else None
        result.append(ScheduledRelease(title,title,d,at,series,category,title.split(',',1)[-1] if ',' in title else None,url))
    if not result: raise ProviderError('BEA has no supported schedule rows')
    return result

def parse_census(body,url):
    soup=BeautifulSoup(body,'html.parser');table=soup.select_one('table#calendar')
    if not table: raise ProviderError('Census calendar structure changed')
    result=[]
    for row in table.select('tr'):
        cells=row.find_all('td',recursive=False)
        if len(cells)<4 or not cells[0].find('a'): continue
        title=cells[0].get_text(' ',strip=True);series,category=classify(title)
        if not series: continue
        d=datetime.strptime(cells[1].get_text(strip=True),'%B %d, %Y').date()
        clock=cells[2].get_text(strip=True)
        at=ny_time(d,clock) if re.fullmatch(r'\d{1,2}:\d{2} [AP]M',clock) else None
        period=cells[3].get_text(' ',strip=True)
        result.append(ScheduledRelease(title+'|'+period,title,d,at,series,category,period,url))
    if not result: raise ProviderError('Census has no retail schedule rows')
    return result

def parse_fomc(body,url):
    soup=BeautifulSoup(body,'html.parser'); result=[]
    for panel in soup.select('.panel'):
        heading=panel.select_one('.panel-heading')
        year=re.search(r'(20\d{2}) FOMC Meetings',heading.get_text(' ',strip=True)) if heading else None
        if not year: continue
        y=int(year[1])
        for i,row in enumerate(panel.select('.fomc-meeting')):
            month=row.select_one('.fomc-meeting__month');days=row.select_one('.fomc-meeting__date')
            if not month or not days: raise ProviderError('FOMC meeting row changed')
            m=month.get_text(strip=True).split('/')[0]; nums=re.findall(r'\d+',days.get_text())
            if not nums: raise ProviderError('FOMC date missing')
            start=datetime.strptime(f'{m[:3]} {nums[0]} {y}','%b %d %Y').date()
            result.append(ScheduledRelease(f'{y}:meeting:{i}','FOMC Meeting',start,None,(),'monetary',days.get_text(' ',strip=True)+' '+month.get_text(' ',strip=True)+' '+str(y),url))
            statement=row.select_one('a[href*="/pressreleases/monetary"][href$="a.htm"]')
            if statement:
                match=re.search(r'monetary(\d{8})a.htm',statement['href'])
                if match:
                    d=datetime.strptime(match[1],'%Y%m%d').date()
                    result.append(ScheduledRelease(f'{y}:statement:{i}','FOMC Statement',d,None,(),'monetary',None,urljoin(url,statement['href']),True))
            minutes=row.select_one('.fomc-meeting__minutes')
            if minutes:
                match=re.search(r'Released\s+(\w+ \d{1,2}, 20\d{2})',minutes.get_text(' ',strip=True))
                link=minutes.select_one('a[href$=".htm"]')
                if match and link:
                    d=datetime.strptime(match[1],'%B %d, %Y').date()
                    result.append(ScheduledRelease(f'{y}:minutes:{i}','FOMC Minutes',d,None,(),'monetary',None,urljoin(url,link['href']),True))
    if not result: raise ProviderError('FOMC panel structure changed')
    return result

def parse_g17(body,url):
    text=BeautifulSoup(body,'html.parser').get_text(' ',strip=True).replace('\xa0',' ')
    if 'monthly releases are issued at 9:15 a.m.' not in text or 'annual revision is issued at noon' not in text:
        raise ProviderError('G17 official time declaration changed')
    block=text.split('The G.17 release will be issued on the following dates.',1)[-1].split('Historical Release Dates')[0]
    sections=re.findall(r'(20\d{2}):\s*(.*?)(?=20\d{2}:|$)',block,re.S)
    result=[]
    for year,section in sections:
        for month,day,note in re.findall(r'([A-Z][a-z]+)\s+(\d{1,2})(\s*\([^)]*\))?',section):
            d=datetime.strptime(f'{month} {day} {year}','%B %d %Y').date()
            annual='annual revision' in note
            result.append(ScheduledRelease(f'{year}:{month}:{"annual" if annual else "monthly"}',
                'Industrial Production'+(' — Annual Revision' if annual else ''),d,ny_time(d,'12:00 PM' if annual else '9:15 AM'),('INDPRO',),'growth',None,url))
    if not result: raise ProviderError('G17 date list changed')
    return result

class OfficialProvider:
    def __init__(self,name,url,parser,settings,urls=None):
        self.name,self.url,self.parser=name,url,parser
        self.urls=urls or [url]; self.transport=FredTransport(settings)
    def fetch(self):
        rows=[]
        try:
            for url in self.urls:
                response=self.transport.request(url,{})
                rows.extend(self.parser(response.text,url))
            return rows
        finally: self.transport.close()

def official_providers(settings):
    return [
        OfficialProvider('bls','https://www.bls.gov/schedule/news_release/bls.ics',parse_ics,settings),
        # BEA's linked ICS is currently stale; use the independently verified current HTML table.
        OfficialProvider('bea','https://www.bea.gov/news/schedule',parse_bea,settings),
        OfficialProvider('census','https://www.census.gov/economic-indicators/calendar-listview.html',parse_census,settings,
            ['https://www.census.gov/economic-indicators/calendar-listview.html',f'https://www.census.gov/economic-indicators/calendar-listview-{date.today().year}.html']),
        OfficialProvider('federal_reserve','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm',parse_fomc,settings),
        OfficialProvider('g17','https://www.federalreserve.gov/releases/g17/',parse_g17,settings),
    ]

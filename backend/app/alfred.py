"""ALFRED through the existing authenticated FRED transport; date precision only."""
from datetime import date
from app.providers import FredAPIProvider,ProviderError,parse_observations

SUPPORTED=('PAYEMS','UNRATE','CPIAUCSL','CPILFESL','PCEPI','PCEPILFE','GDPC1')
EARLIEST=date(1776,7,4)

class AlfredProvider(FredAPIProvider):
    name='alfred'
    def source_date(self,series_id):
        return date.fromisoformat(self.json('series',{'series_id':series_id})['realtime_end'])

    def vintage_dates(self,series_id,start=EARLIEST,end=None):
        end=end or date.today();result=[];offset=0
        while True:
            p=self.json('series/vintagedates',dict(series_id=series_id,realtime_start=str(start),realtime_end=str(end),limit=10000,offset=offset,sort_order='asc'))
            try:
                page=[date.fromisoformat(d) for d in p['vintage_dates']]
                if any(d<start or d>end for d in page):raise ValueError
                count=int(p['count'])
            except (KeyError,TypeError,ValueError):raise ProviderError('Invalid ALFRED vintage catalog') from None
            result+=page;offset+=len(page)
            if offset>=count:break
            if not page:raise ProviderError('ALFRED catalog pagination stalled')
        return sorted(set(result))

    def interval_page(self,series_id,end,offset=0,limit=10000,start=EARLIEST):
        p=self.json('series/observations',dict(series_id=series_id,realtime_start=str(start),realtime_end=str(end),units='lin',output_type=1,limit=limit,offset=offset,sort_order='asc'))
        rows=parse_observations(p)
        for r in rows:
            if r.realtime_start>r.realtime_end or r.realtime_start<start or r.realtime_end>end:
                raise ProviderError('Invalid ALFRED real-time interval')
        return p,rows

    def metadata_history(self,series_id,end):
        p=self.json('series',dict(series_id=series_id,realtime_start=str(EARLIEST),realtime_end=str(end)))
        rows=p.get('seriess')
        if not isinstance(rows,list) or not rows:raise ProviderError('Missing ALFRED metadata history')
        for r in rows:
            if r.get('frequency_short') not in ('M','Q','D'):raise ProviderError('Unsupported ALFRED native frequency')
            for k in ('realtime_start','realtime_end','units','seasonal_adjustment_short'):
                if k not in r:raise ProviderError('ALFRED metadata schema changed')
        return rows

    def snapshot(self,series_id,vintage_date,start=EARLIEST,end=None):
        # output_type=1 with an exact real-time date uses standard value fields.
        result=[];offset=0
        while True:
            p=self.json('series/observations',dict(series_id=series_id,realtime_start=str(vintage_date),realtime_end=str(vintage_date),observation_start=str(start),observation_end=str(end or date.today()),units='lin',output_type=1,limit=100000,offset=offset))
            rows=parse_observations(p);result+=rows;offset+=len(rows)
            if offset>=int(p['count']):return result
            if not rows:raise ProviderError('ALFRED snapshot pagination stalled')

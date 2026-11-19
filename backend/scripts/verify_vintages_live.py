"""Official ALFRED -> archive -> HTTP snapshot acceptance; no invented history."""
import json,hashlib
from datetime import date
from pathlib import Path
import httpx
from sqlalchemy import select,func,text
from app.alfred import AlfredProvider
from app.config import get_settings
from app.db import SessionLocal
from app.vintage_sync import sync_archive
from app.vintage_models import VintageObservation,SeriesVintage,VintageArchive

def main():
    provider=AlfredProvider(get_settings());report={'status':'PASS','checks':[]}
    try:
        with SessionLocal() as db,httpx.Client(base_url='http://127.0.0.1:3000',trust_env=False,timeout=60) as web:
            for sid in ('PAYEMS','GDPC1','PCEPI'):
                archive=db.get(VintageArchive,sid)
                for at in (date(2020,6,15),date(2023,6,15),archive.covered_through):
                    reference=provider.snapshot(sid,at,start=date(2000,1,1))
                    expected={str(r.observation_date):float(r.value) if r.value is not None else None for r in reference if r.observation_date<=at}
                    response=web.get('/api/v1/historical-snapshot',params={'series_id':sid,'as_of':str(at),'start':'2000-01-01','page_size':1000})
                    response.raise_for_status();payload=response.json()
                    assert payload['coverage']=='AVAILABLE' and payload['count']==len(expected),(sid,at,'coverage/count')
                    for p in payload['observations']:
                        assert p['value']==expected[p['date']],(sid,at,p['date'])
                        assert date.fromisoformat(p['vintage_date'])<=at and date.fromisoformat(p['date'])<=at
                    metadata=provider.json('series',dict(series_id=sid,realtime_start=str(at),realtime_end=str(at)))['seriess'][0]
                    assert payload['native_units']==metadata['units']
                    report['checks'].append({'series':sid,'as_of':str(at),'matched_observations':len(expected),'historical_units':payload['native_units'],'future_values':0})
                before=db.scalar(select(func.count()).select_from(VintageObservation).where(VintageObservation.series_id==sid))
                sync_archive(db,provider,sid,force=True)
                assert db.scalar(select(func.count()).select_from(VintageObservation).where(VintageObservation.series_id==sid))==before
            # Recheck all original observations, not a historic assumed row count.
            baseline=json.loads(Path('../.local/iteration3-baseline.json').read_text())
            rows=db.execute(text('select * from observations order by 1')).all()
            assert {'count':len(rows),'sha256':hashlib.sha256(repr(rows).encode()).hexdigest()}==baseline['observations']
            for route in ('/','/calendar','/historical-snapshot','/revisions'):
                assert web.get(route).status_code==200,route
            report.update(vintage_dates=db.scalar(select(func.count()).select_from(SeriesVintage)),vintage_observation_intervals=db.scalar(select(func.count()).select_from(VintageObservation)),original_observations='unchanged checksum',duplicate_sync='PASS',scope='Date-level; no intraday accuracy or certified official initial value')
            print(json.dumps(report,indent=2))
    finally:provider.close()

if __name__=='__main__':main()

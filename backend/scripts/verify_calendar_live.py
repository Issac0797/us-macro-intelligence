"""Live acceptance without inventing a release or altering economic observations."""
import hashlib,json
from pathlib import Path
import httpx
from sqlalchemy import select,text,func
from app.db import SessionLocal
from app.models import Observation
from app.release_models import ReleaseEvent,CalendarProviderState,ReleaseObservation,ScheduleChange
from app.calendar_providers import official_providers
from app.config import get_settings

def main():
    report={'sources':[],'live_release_detection':'PENDING: next actual release; deterministic monitor integration tests cover the update path'}
    with SessionLocal() as db,httpx.Client(base_url='http://127.0.0.1:3000',trust_env=False,timeout=60) as web:
        for p in official_providers(get_settings()):
            state=db.get(CalendarProviderState,p.name)
            try:
                rows=p.fetch()
                for row in rows:
                    eid=hashlib.sha256(f'{p.name}|{row.key}'.encode()).hexdigest()
                    saved=db.get(ReleaseEvent,eid)
                    assert saved is not None, f'Official event missing: {p.name}'
                    assert saved.scheduled_date==row.day
                    if row.at: assert saved.scheduled_at==row.at
                report['sources'].append({'provider':p.name,'verified_events':len({r.key for r in rows}),'status':state.status})
            except Exception as exc:
                if p.name!='bls':raise
                assert state.status in ('BLOCKED','PARTIAL')
                report['sources'].append({'provider':p.name,'status':state.status,'reason':'official endpoint inaccessible'})
        for path in ('/calendar','/api/v1/calendar','/api/v1/calendar/upcoming','/api/v1/revisions','/api/v1/monitor/status','/api/v1/overview'):
            response=web.get(path);assert response.status_code==200,path
        data=web.get('/api/v1/calendar?start=2026-11-01&end=2026-11-30').json()
        for event in data['events']:
            if event['status']!='Released':assert all(i['actual'] is None for i in event['indicators'])
        for event in web.get('/api/v1/calendar/upcoming').json()['events']:
            detail=web.get('/api/v1/releases/'+event['id']);assert detail.status_code==200
            assert web.get('/api/v1/releases/'+event['id']+'/observations').status_code==200
        assert web.get('/api/v1/calendar?tz=bad').json()['error']['code']=='INVALID_INPUT'
        original=db.execute(text('select id,series_id,observation_date,value,raw_value,version from observations where id<=62155 order by id')).all()
        digest=hashlib.sha256(repr(original).encode()).hexdigest()
        assert len(original)==62155 and digest=='7cbf34e6fb3a395a98b3e235a20d1a6efc0af29ce293ee32778131fa77b0c578'
        report.update(original_observations='62155 unchanged; checksum matched',
            observations=db.scalar(select(func.count()).select_from(Observation)),events=db.scalar(select(func.count()).select_from(ReleaseEvent)),
            confirmed_snapshots=db.scalar(select(func.count()).select_from(ReleaseObservation)),
            schedule_changes=db.scalar(select(func.count()).select_from(ScheduleChange)),http_api='PASS')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

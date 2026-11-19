"""Staged/resumable archive refresh. No writes to current observations."""
import argparse,hashlib,json,logging
from datetime import date
from uuid import uuid4
from sqlalchemy import select,delete,text
from app.models import Series,utcnow
from app.vintage_models import VintageArchive,SeriesVintage,VintageObservation,VintageMetadata,VintageSyncJob,VintageSyncPage
from app.alfred import AlfredProvider,SUPPORTED,EARLIEST
from app.providers import ProviderError,parse_observations
from app.config import get_settings
from app.db import SessionLocal
from app.sync import insert_statement
from app.release_service import aware

def sync_archive(db,provider,sid,force=False,end=None,restart=False):
    end=end or (provider.source_date(sid) if hasattr(provider,'source_date') else date.today())
    if sid not in SUPPORTED or not db.get(Series,sid):raise ValueError('Unsupported vintage series')
    # Session advisory lock persists across page commits. One importer per series.
    lock=None
    if db.bind.dialect.name=='postgresql':
        lock=db.bind.connect();lock_key=int.from_bytes(hashlib.sha256(('alfred:'+sid).encode()).digest()[:8],'big',signed=True)
        if not lock.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':lock_key}):lock.close();raise ProviderError('Vintage sync already running')
    job=None
    try:
        archive=db.get(VintageArchive,sid)
        if restart:
            for stale in db.scalars(select(VintageSyncJob).where(VintageSyncJob.series_id==sid,VintageSyncJob.status.in_(['failed','running']))):stale.status='abandoned'
            db.commit()
        if archive and archive.status=='complete' and archive.covered_through>=end and not force and (utcnow()-aware(archive.retrieved_at)).total_seconds()<get_settings().vintage_cache_seconds:return archive
        job=db.scalar(select(VintageSyncJob).where(VintageSyncJob.series_id==sid,VintageSyncJob.status.in_(['running','failed']),VintageSyncJob.end_vintage==end).order_by(VintageSyncJob.started_at.desc()).limit(1))
        if not job:
            job=VintageSyncJob(id=str(uuid4()),series_id=sid,start_vintage=EARLIEST,end_vintage=end,status='running',checkpoint=0,attempts=0)
            db.add(job);db.commit()
        job.status='running';job.attempts+=1;job.last_error=None;db.commit()
        if not job.catalog_json:
            job.catalog_json=json.dumps([str(d) for d in provider.vintage_dates(sid,end=end)])
            job.metadata_json=json.dumps(provider.metadata_history(sid,end));db.commit()
        while job.expected_count is None or job.checkpoint<job.expected_count:
            payload,rows=provider.interval_page(sid,end,job.checkpoint)
            expected=int(payload['count'])
            if job.expected_count is not None and job.expected_count!=expected:raise ProviderError('Source changed during pagination; restart with a new pinned date')
            if expected and not rows:raise ProviderError('ALFRED interval pagination stalled')
            raw=json.dumps(payload['observations'],sort_keys=True)
            db.add(VintageSyncPage(job_id=job.id,offset=job.checkpoint,payload=raw,sha256=hashlib.sha256(raw.encode()).hexdigest()))
            job.expected_count=expected;job.checkpoint+=len(rows);db.commit()
            if not expected:break
        # Validate all staged records before atomically replacing the served archive.
        all_rows=[]
        for page in db.scalars(select(VintageSyncPage).where(VintageSyncPage.job_id==job.id).order_by(VintageSyncPage.offset)):
            if hashlib.sha256(page.payload.encode()).hexdigest()!=page.sha256:raise ProviderError('Staged page checksum mismatch')
            all_rows+=parse_observations({'observations':json.loads(page.payload)})
        if len(all_rows)!=job.expected_count:raise ProviderError('Incomplete ALFRED archive')
        grouped={}
        for r in all_rows:
            key=(r.observation_date,r.realtime_start)
            if key in grouped:raise ProviderError('Duplicate ALFRED interval key')
            grouped[key]=r
        previous={}
        for r in sorted(all_rows,key=lambda r:(r.observation_date,r.realtime_start)):
            if r.observation_date in previous and previous[r.observation_date]>=r.realtime_start:raise ProviderError('Overlapping ALFRED intervals')
            previous[r.observation_date]=r.realtime_end
        retrieved=utcnow();dates=[date.fromisoformat(d) for d in json.loads(job.catalog_json)]
        metadata=json.loads(job.metadata_json)
        db.execute(delete(VintageObservation).where(VintageObservation.series_id==sid))
        db.execute(delete(VintageMetadata).where(VintageMetadata.series_id==sid))
        db.execute(delete(SeriesVintage).where(SeriesVintage.series_id==sid))
        for start in range(0,len(all_rows),500):
            values=[dict(series_id=sid,observation_date=r.observation_date,vintage_date=r.realtime_start,realtime_end=r.realtime_end,value=r.value,raw_value=r.raw_value,retrieved_at=retrieved,source='ALFRED') for r in all_rows[start:start+500]]
            db.execute(insert_statement(db,VintageObservation).values(values))
        for start in range(0,len(dates),500):
            values=[dict(series_id=sid,vintage_date=d,source='ALFRED',retrieved_at=retrieved,sync_status='complete') for d in dates[start:start+500]]
            if values:db.execute(insert_statement(db,SeriesVintage).values(values))
        for m in metadata:
            db.add(VintageMetadata(series_id=sid,realtime_start=date.fromisoformat(m['realtime_start']),realtime_end=date.fromisoformat(m['realtime_end']),units=m['units'],frequency={'M':'monthly','Q':'quarterly','D':'daily'}[m['frequency_short']],seasonal_adjustment=m['seasonal_adjustment_short'],retrieved_at=retrieved))
        if not archive:archive=VintageArchive(series_id=sid);db.add(archive)
        archive.status='complete';archive.first_vintage=min(dates) if dates else None;archive.covered_through=end;archive.retrieved_at=retrieved
        archive.fingerprint=hashlib.sha256(''.join(f'{r.observation_date}|{r.realtime_start}|{r.realtime_end}|{r.raw_value}' for r in all_rows).encode()).hexdigest()
        job.status='complete';job.finished_at=retrieved
        db.commit()
        # Pages remain as verifiable response cache/provenance for this job.
        logging.info('ALFRED complete series=%s vintages=%s intervals=%s',sid,len(dates),len(all_rows))
        return archive
    except Exception as exc:
        db.rollback()
        if job:
            job=db.get(VintageSyncJob,job.id);job.status='failed';job.last_error=f'{type(exc).__name__}: archive sync failed; resume checkpoint retained';db.commit()
        raise
    finally:
        if lock:
            lock.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':lock_key});lock.commit();lock.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--series',nargs='+',default=list(SUPPORTED));p.add_argument('--force',action='store_true');p.add_argument('--restart',action='store_true');args=p.parse_args()
    logging.basicConfig(level=logging.INFO);logging.getLogger('httpx').setLevel(logging.WARNING)
    provider=AlfredProvider(get_settings())
    try:
        with SessionLocal() as db:
            for sid in args.series:sync_archive(db,provider,sid,args.force or args.restart,restart=args.restart)
    finally:provider.close()

if __name__=='__main__':main()

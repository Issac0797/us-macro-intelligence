"""Single-process, restartable calendar and release worker. No broker required."""
import argparse
import logging
import time
from sqlalchemy import select
from app.config import get_settings
from app.db import SessionLocal
from app.models import utcnow,Observation
from app.release_models import CalendarProviderState,ReleaseMonitorJob
from app.release_service import refresh_calendar,seed_extended,run_job,aware
from app.calendar_providers import official_providers
from app.providers import get_provider
from app.sync import seed_catalog,sync_series

def cycle(calendar=True):
    settings=get_settings();now=utcnow()
    with SessionLocal() as session:
        seed_catalog(session);seed_extended(session)
        if calendar:
            for provider in official_providers(settings):
                state=session.get(CalendarProviderState,provider.name)
                if not state or (now-aware(state.last_attempt_at)).total_seconds()>=settings.calendar_refresh_seconds:
                    result=refresh_calendar(session,provider,now)
                    logging.info('Calendar provider=%s status=%s events=%s',provider.name,result.status,result.event_count)
                else:
                    provider.transport.close()
        provider=get_provider(settings)
        try:
            jobs=list(session.scalars(select(ReleaseMonitorJob).where(ReleaseMonitorJob.status.in_(['waiting','running','failed']),ReleaseMonitorJob.next_retry_at<=now).order_by(ReleaseMonitorJob.next_retry_at).limit(100)))
            for job in jobs: run_job(session,job.event_id,provider,settings)
        finally: provider.close()
        # Official policy refresh is isolated from macro and calendar providers.
        try:
            from app.fed.models import SyncJob as FedJob
            from app.fed.sync import sync_fed,sync_rates
            last=session.scalar(select(FedJob).order_by(FedJob.id.desc()).limit(1))
            if not last or (now-aware(last.started_at)).total_seconds()>=21600:
                sync_fed(session)
                try:sync_rates(session)
                except Exception as exc:
                    session.rollback();logging.error('Fed rate refresh failed type=%s',type(exc).__name__)
        except Exception as exc:
            session.rollback()
            logging.error('Fed refresh failed type=%s',type(exc).__name__)
        # Refresh established ALFRED archives daily, independently of calendar coverage.
        from app.vintage_models import VintageArchive
        from app.vintage_sync import sync_archive
        from app.alfred import AlfredProvider
        from datetime import date
        due=list(session.scalars(select(VintageArchive).where(VintageArchive.covered_through<date.today())))
        if due:
            alfred=AlfredProvider(settings)
            try:
                source_day=alfred.source_date(due[0].series_id)
                for archive in due:
                    if archive.covered_through>=source_day:continue
                    try:sync_archive(session,alfred,archive.series_id)
                    except Exception as exc:logging.error('ALFRED refresh failed series=%s type=%s',archive.series_id,type(exc).__name__)
            finally:alfred.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--force-calendar',action='store_true');parser.add_argument('--bootstrap',action='store_true');args=parser.parse_args()
    logging.basicConfig(level=logging.INFO);logging.getLogger('httpx').setLevel(logging.WARNING)
    with SessionLocal() as session:
        seed_catalog(session);seed_extended(session)
        if args.bootstrap:
            provider=get_provider(get_settings())
            try:
                from app.release_service import EXTRA_SERIES
                for sid,*_ in EXTRA_SERIES:
                    if session.scalar(select(Observation.id).where(Observation.series_id==sid).limit(1)) is None:
                        sync_series(session,provider,sid,full=True)
            finally: provider.close()
    if args.force_calendar:
        with SessionLocal() as session:
            for p in official_providers(get_settings()): refresh_calendar(session,p)
    from concurrent.futures import ThreadPoolExecutor
    from app.sync_schedule import reconcile_due
    pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='series-reconciliation')
    pending=None
    while True:
        if pending is None or pending.done():
            if pending is not None:
                try:pending.result()
                except Exception as exc:logging.error('Series scheduler failed type=%s',type(exc).__name__)
            pending=pool.submit(reconcile_due)
        try: cycle()
        except Exception as exc:
            logging.error('Monitor cycle failed type=%s',type(exc).__name__)
            if args.once: raise SystemExit(1) from None
        if args.once:
            pending.result();pool.shutdown(wait=True);break
        time.sleep(30)

if __name__=='__main__': main()

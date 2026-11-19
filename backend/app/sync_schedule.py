"""Independent series reconciliation. Persist progress in existing immutable SyncTask rows."""
from datetime import timedelta
from sqlalchemy import select, func
from app.models import Series, Observation, SyncTask, utcnow
from app.release_service import aware


def sync_states(db, now=None):
    now = now or utcnow()
    ranked = select(SyncTask.id, func.row_number().over(partition_by=SyncTask.series_id,
        order_by=(SyncTask.started_at.desc(), SyncTask.id.desc())).label('rn')).subquery()
    tasks = {t.series_id: t for t in db.scalars(select(SyncTask).join(ranked, ranked.c.id == SyncTask.id).where(ranked.c.rn == 1))}
    latest = dict(db.execute(select(Observation.series_id, func.max(Observation.observation_date)).group_by(Observation.series_id)).all())
    result = []
    for s in db.scalars(select(Series).order_by(Series.id)):
        t = tasks.get(s.id)
        attempt = aware(t.started_at) if t else None
        success = aware(s.last_synced_at)
        interval = 3600 if s.frequency in ('daily', 'weekly') else 21600
        state = 'IDLE'
        if t:
            if t.status == 'running':
                # A process crash leaves an auditable expired attempt, eligible for compensation.
                state = 'RUNNING' if (now-attempt).total_seconds() < 1800 else 'FAILED'
            elif t.status == 'succeeded':
                state = 'SUCCESS' if t.rows_inserted else 'NO_NEW_OBSERVATION'
            else:
                state = 'SOURCE_BLOCKED' if 'HTTP_403' in (t.error or '') else 'RETRYING'
        delay = 300 if state in ('FAILED', 'RETRYING') else 21600 if state == 'SOURCE_BLOCKED' else interval
        due = (attempt or now-timedelta(seconds=delay)) + timedelta(seconds=delay)
        if state == 'RUNNING':
            due = attempt + timedelta(seconds=1800)
        result.append(dict(series_id=s.id, frequency=s.frequency, state=state,
            latest_observation_date=latest.get(s.id), last_successful_sync=success, last_attempt=attempt,
            next_scheduled_attempt=due, source_status='BLOCKED' if state == 'SOURCE_BLOCKED' else 'ERROR' if state in ('FAILED','RETRYING') else 'OK' if success else 'UNKNOWN',
            last_error=t.error if t else None))
    return result


def reconcile_due(provider=None, now=None):
    """Separate monitor thread/session/transport: slow calendar/Fed cannot block ordinary series."""
    from app.db import SessionLocal
    from app.providers import get_provider
    from app.config import get_settings
    from app.sync import sync_series
    now = now or utcnow()
    owned = provider is None
    provider = provider or get_provider(get_settings())
    results = []
    try:
        with SessionLocal() as db:
            due = [s for s in sync_states(db, now) if s['next_scheduled_attempt'] <= now and s['state'] != 'RUNNING']
        for s in due:
            with SessionLocal() as db:
                try:
                    task = sync_series(db, provider, s['series_id'])
                    results.append((s['series_id'], task.status, task.rows_inserted))
                except Exception as exc:
                    # sync_series records the safe failure; each subsequent series still runs.
                    results.append((s['series_id'], type(exc).__name__, 0))
    finally:
        if owned:
            provider.close()
    return results

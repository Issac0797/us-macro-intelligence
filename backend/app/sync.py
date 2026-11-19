import argparse
import hashlib
import logging
import time
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.catalog import CATALOG
from app.config import get_settings
from app.db import SessionLocal
from app.models import Observation, Series, SyncTask, utcnow
from app.providers import get_provider

log = logging.getLogger(__name__)


def insert_statement(session, model):
    return (pg_insert if session.bind.dialect.name == "postgresql" else sqlite_insert)(model)


def seed_catalog(session):
    for item in CATALOG:
        stmt = insert_statement(session, Series).values(**item, source="FRED",
            source_url=f"https://fred.stlouisfed.org/series/{item['id']}")
        session.execute(stmt.on_conflict_do_nothing(index_elements=["id"]))
    session.commit()


def latest_observations(session, series_id, as_of=None):
    query = select(Observation).where(Observation.series_id == series_id)
    if as_of:
        query = query.where(Observation.collected_at <= as_of)
    # Rank before date filtering; one immutable local revision per observation date.
    ranked = query.with_only_columns(Observation.id,
        func.row_number().over(partition_by=Observation.observation_date,
            order_by=(Observation.collected_at.desc(), Observation.id.desc())).label("rn")).subquery()
    return select(Observation).join(ranked, Observation.id == ranked.c.id).where(ranked.c.rn == 1).order_by(Observation.observation_date)


def sync_series(session, provider, series_id: str, full=False, settings=None):
    settings = settings or get_settings()
    series = session.get(Series, series_id)
    if series is None:
        raise ValueError(f"Unknown series: {series_id}")
    latest_date = session.scalar(select(func.max(Observation.observation_date)).where(Observation.series_id == series_id))
    start = settings.sync_start_date if full or latest_date is None else max(settings.sync_start_date, latest_date - timedelta(days=settings.sync_lookback_days))
    task_id = str(uuid4())
    task = SyncTask(id=task_id, series_id=series_id, provider=provider.name, mode="full" if full else "incremental",
                    status="running", observation_start=start, observation_end=date.today())
    session.add(task)
    session.commit()
    try:
        # Transaction-scoped lock prevents competing imports from duplicating revision chains.
        if session.bind.dialect.name == "postgresql":
            lock_id = int.from_bytes(hashlib.sha256(series_id.encode()).digest()[:8], "big", signed=True)
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
        metadata = provider.metadata(series_id)
        rows = provider.observations(series_id, start, date.today())
        for key, value in metadata.items():
            setattr(series, key, value)
        from app.read_queries import observation_rows
        existing = {o.observation_date: o for o in session.execute(observation_rows(session, series_id, start=start))}
        inserted, collected = 0, utcnow()
        pending = []
        if len({row.observation_date for row in rows}) != len(rows):
            raise ValueError("Duplicate observation dates in provider snapshot")
        for row in rows:
            previous = existing.get(row.observation_date)
            if previous and (previous.raw_value, previous.units, previous.source) == (row.raw_value, series.units, provider.name):
                continue
            # Chained content hash preserves A -> B -> A revisions while repeats are no-ops.
            version = hashlib.sha256(f"{previous.version if previous else ''}|{row.raw_value}|{series.units}|{provider.name}".encode()).hexdigest()
            values = dict(series_id=series_id, observation_date=row.observation_date, value=row.value,
                raw_value=row.raw_value, units=series.units, source=provider.name, source_url=series.source_url,
                version=version, realtime_start=row.realtime_start, realtime_end=row.realtime_end,
                collected_at=collected, released_at=None)
            pending.append(values)
        for offset in range(0, len(pending), 500):
            stmt = insert_statement(session, Observation).values(pending[offset:offset + 500]).on_conflict_do_nothing(
                index_elements=["series_id", "observation_date", "version"]).returning(Observation.id)
            inserted += len(session.scalars(stmt).all())
        from app.release_models import ObservationRevision
        for values in pending:
            previous = existing.get(values['observation_date'])
            if previous:
                delta = (values['value'] - previous.value) if values['value'] is not None and previous.value is not None and values['units'] == previous.units else None
                stmt = insert_statement(session, ObservationRevision).values(
                    series_id=series_id, observation_date=values['observation_date'],
                    old_value=previous.value, new_value=values['value'], delta=delta,
                    old_version=previous.version, new_version=values['version'],
                    old_units=previous.units, new_units=values['units'], detected_at=collected,
                    source=provider.name, scope='local_sync_diff').on_conflict_do_nothing(
                        index_elements=['series_id','observation_date','new_version'])
                session.execute(stmt)
        task.rows_received, task.rows_inserted = len(rows), inserted
        task.status, task.finished_at = "succeeded", utcnow()
        series.last_synced_at = collected
        session.commit()
        log.info("Sync succeeded series=%s provider=%s received=%s inserted=%s", series_id, provider.name, len(rows), inserted)
        return task
    except Exception as exc:
        session.rollback()
        task = session.get(SyncTask, task_id)
        # No raw exception messages: HTTP exceptions can contain a credential-bearing URL.
        task.status, task.finished_at, task.error = "failed", utcnow(), f"{type(exc).__name__}: HTTP_{getattr(exc, 'status_code', None)} sync failed; check provider connectivity/configuration"
        session.commit()
        log.error("Sync failed series=%s provider=%s error_type=%s", series_id, provider.name, type(exc).__name__)
        raise


def main():
    parser = argparse.ArgumentParser(description="Import real FRED observations")
    parser.add_argument("--full", action="store_true", help="Recheck full history, including older revisions")
    parser.add_argument("--series", nargs="+", help="FRED series IDs; default all catalog series")
    parser.add_argument("--interval", type=int, default=0, help="Repeat every N seconds; 0 runs once")
    args = parser.parse_args()
    if args.interval and args.interval < 60:
        parser.error("interval must be at least 60 seconds")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx INFO logging includes URLs. Keep it disabled to protect API keys.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    provider = get_provider(get_settings())
    try:
        while True:
            failures = 0
            with SessionLocal() as session:
                seed_catalog(session)
                for series_id in args.series or [s["id"] for s in CATALOG]:
                    try:
                        sync_series(session, provider, series_id, args.full)
                    except Exception:
                        failures += 1
            if not args.interval:
                if failures:
                    raise SystemExit(1)
                break
            time.sleep(args.interval)
    finally:
        provider.close()


if __name__ == "__main__":
    main()

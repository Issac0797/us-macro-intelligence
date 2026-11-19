from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.config import Settings
from app.models import Observation, Series, SyncTask
from app.providers import Datum, ProviderError
from app.sync import latest_observations, seed_catalog, sync_series


class FakeProvider:
    name = "fred_csv"
    rows = [Datum(date(2024, 1, 1), Decimal("100"), "100"), Datum(date(2024, 2, 1), None, ".")]
    def metadata(self, series_id):
        return {}
    def observations(self, series_id, start, end):
        self.start = start
        return self.rows


def test_repeat_sync_is_idempotent_and_missing_preserved(db):
    seed_catalog(db)
    provider = FakeProvider()
    first = sync_series(db, provider, "CPIAUCSL")
    second = sync_series(db, provider, "CPIAUCSL")
    assert (first.rows_inserted, second.rows_inserted) == (2, 0)
    assert db.scalar(select(func.count()).select_from(Series)) == 10
    assert db.scalar(select(func.count()).select_from(Observation)) == 2
    missing = db.scalar(select(Observation).where(Observation.value.is_(None)))
    assert missing.raw_value == "." and missing.units == "Index 1982-1984=100"
    assert missing.released_at is None and missing.realtime_start is None
    assert missing.collected_at is not None and missing.source == "fred_csv"


def test_revisions_and_reverting_values(db):
    provider = FakeProvider()
    sync_series(db, provider, "CPIAUCSL")
    cutoff = db.scalar(select(Observation).limit(1)).collected_at + timedelta(microseconds=1)
    provider.rows = [Datum(date(2024, 1, 1), Decimal("101"), "101")]
    sync_series(db, provider, "CPIAUCSL")
    assert list(db.scalars(latest_observations(db, "CPIAUCSL")))[0].value == 101
    assert list(db.scalars(latest_observations(db, "CPIAUCSL", cutoff)))[0].value == 100
    provider.rows = [Datum(date(2024, 1, 1), Decimal("100"), "100")]
    sync_series(db, provider, "CPIAUCSL")
    sync_series(db, provider, "CPIAUCSL")
    assert db.scalar(select(func.count()).select_from(Observation)) == 4
    assert list(db.scalars(latest_observations(db, "CPIAUCSL")))[0].value == 100


def test_failed_sync_is_recorded_and_atomic(db):
    class Broken(FakeProvider):
        def observations(self, *args):
            raise ProviderError("test failure containing secret")
    with pytest.raises(ProviderError):
        sync_series(db, Broken(), "CPIAUCSL")
    task = db.scalar(select(SyncTask))
    assert task.status == "failed" and task.finished_at is not None
    assert "secret" not in task.error
    assert db.scalar(select(func.count()).select_from(Observation)) == 0


def test_incremental_lookback_and_full(db):
    provider = FakeProvider()
    settings = Settings(_env_file=None, sync_start_date=date(2000, 1, 1), sync_lookback_days=400)
    sync_series(db, provider, "CPIAUCSL", settings=settings)
    assert provider.start == date(2000, 1, 1)
    sync_series(db, provider, "CPIAUCSL", settings=settings)
    assert provider.start == date(2024, 2, 1) - timedelta(days=400)
    sync_series(db, provider, "CPIAUCSL", full=True, settings=settings)
    assert provider.start == date(2000, 1, 1)


def test_duplicate_dates_are_rejected_atomically(db):
    provider = FakeProvider()
    provider.rows = [provider.rows[0], provider.rows[0]]
    with pytest.raises(ValueError, match="Duplicate observation dates"):
        sync_series(db, provider, "CPIAUCSL")
    assert db.scalar(select(func.count()).select_from(Observation)) == 0
    assert db.scalar(select(SyncTask)).status == "failed"


def test_batch_boundary_idempotent(db):
    provider = FakeProvider()
    provider.rows = [Datum(date(2024, 1, 1) + timedelta(days=i), Decimal(i + 1), str(i + 1)) for i in range(501)]
    assert sync_series(db, provider, "DFF").rows_inserted == 501
    assert sync_series(db, provider, "DFF").rows_inserted == 0
    assert db.scalar(select(func.count()).select_from(Observation)) == 501

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Series(Base):
    __tablename__ = "series"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    short_name: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(32), index=True)
    frequency: Mapped[str] = mapped_column(String(20))
    units: Mapped[str] = mapped_column(String(150))
    unit_kind: Mapped[str] = mapped_column(String(20))
    seasonal_adjustment: Mapped[str] = mapped_column(String(80))
    agency: Mapped[str] = mapped_column(String(200))
    default_transform: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(40), default="FRED")
    source_url: Mapped[str] = mapped_column(String(300))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("series_id", "observation_date", "version", name="uq_observation_version"),
        Index("ix_observation_latest", "series_id", "observation_date", "collected_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id"))
    observation_date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 10))
    raw_value: Mapped[str] = mapped_column(String(80))
    units: Mapped[str] = mapped_column(String(150))
    source: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str] = mapped_column(String(300))
    version: Mapped[str] = mapped_column(String(64))
    realtime_start: Mapped[date | None] = mapped_column(Date)
    realtime_end: Mapped[date | None] = mapped_column(Date)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncTask(Base):
    __tablename__ = "sync_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("series.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observation_start: Mapped[date] = mapped_column(Date)
    observation_end: Mapped[date] = mapped_column(Date)
    rows_received: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

# Register additive Iteration 2 tables with the same metadata/Alembic target.
from app import release_models  # noqa: E402,F401
from app import vintage_models  # noqa: E402,F401
from app import workspace_models  # noqa: E402,F401
from app.fed import models as fed_models  # noqa: E402,F401

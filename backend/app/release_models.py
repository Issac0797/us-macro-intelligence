from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base, utcnow

class ReleaseEvent(Base):
    __tablename__ = 'release_events'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    source_key: Mapped[str] = mapped_column(String(400))
    release_name: Mapped[str] = mapped_column(String(400))
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    actual_released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reference_period: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(32))
    importance: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default='Unknown')
    source_url: Mapped[str] = mapped_column(String(1000))
    source_name: Mapped[str] = mapped_column(String(100))
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class ReleaseEventSeries(Base):
    __tablename__ = 'release_event_series'
    event_id: Mapped[str] = mapped_column(ForeignKey('release_events.id'), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey('series.id'), primary_key=True)
    baseline_date: Mapped[date | None] = mapped_column(Date)
    baseline_version: Mapped[str | None] = mapped_column(String(64))

class ReleaseObservation(Base):
    __tablename__ = 'release_observations'
    event_id: Mapped[str] = mapped_column(ForeignKey('release_events.id'), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey('series.id'), primary_key=True)
    observation_date: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24,10))
    previous_value: Mapped[Decimal | None] = mapped_column(Numeric(24,10))
    version: Mapped[str] = mapped_column(String(64))
    units: Mapped[str] = mapped_column(String(150))
    source: Mapped[str] = mapped_column(String(40))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ObservationRevision(Base):
    __tablename__ = 'observation_revisions'
    __table_args__ = (UniqueConstraint('series_id','observation_date','new_version', name='uq_revision_version'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey('series.id'), index=True)
    observation_date: Mapped[date] = mapped_column(Date)
    old_value: Mapped[Decimal | None] = mapped_column(Numeric(24,10))
    new_value: Mapped[Decimal | None] = mapped_column(Numeric(24,10))
    delta: Mapped[Decimal | None] = mapped_column(Numeric(24,10))
    old_version: Mapped[str] = mapped_column(String(64))
    new_version: Mapped[str] = mapped_column(String(64))
    old_units: Mapped[str] = mapped_column(String(150))
    new_units: Mapped[str] = mapped_column(String(150))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(40))
    scope: Mapped[str] = mapped_column(String(32), default='local_sync_diff')

class ReleaseMonitorJob(Base):
    __tablename__ = 'release_monitor_jobs'
    event_id: Mapped[str] = mapped_column(ForeignKey('release_events.id'), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default='waiting')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))

class ScheduleChange(Base):
    __tablename__ = 'release_schedule_changes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey('release_events.id'), index=True)
    old_snapshot: Mapped[str] = mapped_column(Text)
    new_snapshot: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class CalendarProviderState(Base):
    __tablename__ = 'calendar_provider_states'
    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    source_url: Mapped[str] = mapped_column(String(1000))
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))
    event_count: Mapped[int] = mapped_column(Integer, default=0)

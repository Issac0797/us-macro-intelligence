from datetime import date,datetime
from decimal import Decimal
from sqlalchemy import String,Integer,Date,DateTime,Numeric,Text,ForeignKey,Index,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.models import Base,utcnow

class VintageArchive(Base):
    __tablename__='vintage_archives'
    series_id:Mapped[str]=mapped_column(ForeignKey('series.id'),primary_key=True)
    first_vintage:Mapped[date|None]=mapped_column(Date)
    covered_through:Mapped[date|None]=mapped_column(Date)
    retrieved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    status:Mapped[str]=mapped_column(String(24),default='pending')
    fingerprint:Mapped[str|None]=mapped_column(String(64))

class SeriesVintage(Base):
    __tablename__='series_vintages'
    series_id:Mapped[str]=mapped_column(ForeignKey('series.id'),primary_key=True)
    vintage_date:Mapped[date]=mapped_column(Date,primary_key=True)
    source:Mapped[str]=mapped_column(String(32),default='ALFRED')
    retrieved_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    sync_status:Mapped[str]=mapped_column(String(24),default='complete')

class VintageObservation(Base):
    __tablename__='vintage_observations'
    __table_args__=(Index('ix_vintage_pit','series_id','vintage_date','realtime_end','observation_date'),)
    series_id:Mapped[str]=mapped_column(ForeignKey('series.id'),primary_key=True)
    observation_date:Mapped[date]=mapped_column(Date,primary_key=True)
    vintage_date:Mapped[date]=mapped_column(Date,primary_key=True)
    realtime_end:Mapped[date]=mapped_column(Date)
    value:Mapped[Decimal|None]=mapped_column(Numeric(24,10))
    raw_value:Mapped[str]=mapped_column(String(80))
    retrieved_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    source:Mapped[str]=mapped_column(String(32),default='ALFRED')

class VintageMetadata(Base):
    __tablename__='vintage_metadata'
    series_id:Mapped[str]=mapped_column(ForeignKey('series.id'),primary_key=True)
    realtime_start:Mapped[date]=mapped_column(Date,primary_key=True)
    realtime_end:Mapped[date]=mapped_column(Date)
    units:Mapped[str]=mapped_column(String(150))
    frequency:Mapped[str]=mapped_column(String(20))
    seasonal_adjustment:Mapped[str]=mapped_column(String(32))
    retrieved_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))

class VintageSyncJob(Base):
    __tablename__='vintage_sync_jobs'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    series_id:Mapped[str]=mapped_column(ForeignKey('series.id'),index=True)
    start_vintage:Mapped[date]=mapped_column(Date)
    end_vintage:Mapped[date]=mapped_column(Date)
    status:Mapped[str]=mapped_column(String(24))
    checkpoint:Mapped[int]=mapped_column(Integer,default=0)
    expected_count:Mapped[int|None]=mapped_column(Integer)
    attempts:Mapped[int]=mapped_column(Integer,default=0)
    last_error:Mapped[str|None]=mapped_column(String(300))
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    catalog_json:Mapped[str|None]=mapped_column(Text)
    metadata_json:Mapped[str|None]=mapped_column(Text)

class VintageSyncPage(Base):
    __tablename__='vintage_sync_pages'
    job_id:Mapped[str]=mapped_column(ForeignKey('vintage_sync_jobs.id'),primary_key=True)
    offset:Mapped[int]=mapped_column(Integer,primary_key=True)
    payload:Mapped[str]=mapped_column(Text)
    sha256:Mapped[str]=mapped_column(String(64))

class ReleaseMonitorAudit(Base):
    __tablename__='release_monitor_audits'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    event_id:Mapped[str]=mapped_column(ForeignKey('release_events.id'),index=True)
    scheduled_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    check_started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    check_finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    first_detected_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    updated_rows:Mapped[int]=mapped_column(Integer,default=0)
    attempts:Mapped[int]=mapped_column(Integer)
    status:Mapped[str]=mapped_column(String(32))
    error:Mapped[str|None]=mapped_column(String(300))

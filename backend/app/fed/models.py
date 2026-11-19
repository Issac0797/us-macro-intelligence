"""Additive official policy research storage. Raw versions never overwrite evidence."""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Text, Date, DateTime, Integer, Numeric, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models import Base, utcnow

class Meeting(Base):
 __tablename__='fomc_meetings'
 id:Mapped[str]=mapped_column(String(10),primary_key=True)
 start_date:Mapped[date]=mapped_column(Date)
 end_date:Mapped[date]=mapped_column(Date,index=True)
 source_url:Mapped[str]=mapped_column(String(500))
 verified_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
 calendar_event_id:Mapped[str|None]=mapped_column(String(100))

class Document(Base):
 __tablename__='fomc_documents'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 meeting_id:Mapped[str]=mapped_column(ForeignKey('fomc_meetings.id'),index=True)
 kind:Mapped[str]=mapped_column(String(30))
 source_url:Mapped[str]=mapped_column(String(500),unique=True)
 published_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),index=True)
 precision:Mapped[str]=mapped_column(String(20),default='UNKNOWN')
 publication_evidence:Mapped[str|None]=mapped_column(Text)
 content_hash:Mapped[str|None]=mapped_column(String(64))
 raw_html:Mapped[str|None]=mapped_column(Text)
 content:Mapped[dict|None]=mapped_column(JSON)
 status:Mapped[str]=mapped_column(String(40),default='DETECTED')
 first_detected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
 retrieved_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 parsed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 attempts:Mapped[int]=mapped_column(Integer,default=0)
 error:Mapped[str|None]=mapped_column(Text)

class DocumentVersion(Base):
 __tablename__='fomc_document_versions'
 __table_args__=(UniqueConstraint('document_id','content_hash',name='uq_fed_document_hash'),)
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 document_id:Mapped[int]=mapped_column(ForeignKey('fomc_documents.id'),index=True)
 content_hash:Mapped[str]=mapped_column(String(64))
 raw_html:Mapped[str]=mapped_column(Text)
 detected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class Decision(Base):
 __tablename__='fomc_decisions'
 meeting_id:Mapped[str]=mapped_column(ForeignKey('fomc_meetings.id'),primary_key=True)
 document_id:Mapped[int]=mapped_column(ForeignKey('fomc_documents.id'))
 lower:Mapped[Decimal]=mapped_column(Numeric(8,4))
 upper:Mapped[Decimal]=mapped_column(Numeric(8,4))
 change_bp:Mapped[Decimal|None]=mapped_column(Numeric(8,2))
 effective_date:Mapped[date|None]=mapped_column(Date)
 effective_document_id:Mapped[int|None]=mapped_column(ForeignKey('fomc_documents.id'))
 vote_for:Mapped[int|None]=mapped_column(Integer)
 vote_against:Mapped[int|None]=mapped_column(Integer)
 dissent:Mapped[str|None]=mapped_column(Text)

class Projection(Base):
 __tablename__='fomc_sep_projections'
 __table_args__=(UniqueConstraint('document_id','variable','target_year','statistic','is_previous',name='uq_fed_sep_cell'),)
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 document_id:Mapped[int]=mapped_column(ForeignKey('fomc_documents.id'),index=True)
 meeting_id:Mapped[str]=mapped_column(ForeignKey('fomc_meetings.id'),index=True)
 variable:Mapped[str]=mapped_column(String(40))
 target_year:Mapped[str]=mapped_column(String(12))
 statistic:Mapped[str]=mapped_column(String(24))
 is_previous:Mapped[bool]=mapped_column(default=False)
 value:Mapped[Decimal|None]=mapped_column(Numeric(10,4))
 low:Mapped[Decimal|None]=mapped_column(Numeric(10,4))
 high:Mapped[Decimal|None]=mapped_column(Numeric(10,4))
 raw_value:Mapped[str]=mapped_column(String(80))

class Dot(Base):
 __tablename__='fomc_dot_distributions'
 __table_args__=(UniqueConstraint('document_id','target_year','rate',name='uq_fed_dot_cell'),)
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 document_id:Mapped[int]=mapped_column(ForeignKey('fomc_documents.id'),index=True)
 meeting_id:Mapped[str]=mapped_column(ForeignKey('fomc_meetings.id'),index=True)
 target_year:Mapped[str]=mapped_column(String(12))
 rate:Mapped[Decimal]=mapped_column(Numeric(8,4))
 participants:Mapped[int]=mapped_column(Integer)

class SyncJob(Base):
 __tablename__='fomc_sync_jobs'
 id:Mapped[int]=mapped_column(Integer,primary_key=True)
 status:Mapped[str]=mapped_column(String(40))
 checkpoint:Mapped[str|None]=mapped_column(String(500))
 started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
 finished_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
 attempts:Mapped[int]=mapped_column(Integer,default=0)
 errors:Mapped[list]=mapped_column(JSON,default=list)
 counts:Mapped[dict]=mapped_column(JSON,default=dict)

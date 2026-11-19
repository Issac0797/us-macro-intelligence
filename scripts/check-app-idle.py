"""Refuse application switching while recent persisted sync work is running."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import text
from app.db import engine
with engine.connect() as db:
    counts={}
    for table,column in [('sync_tasks','started_at'),('vintage_sync_jobs','started_at'),('fomc_sync_jobs','started_at')]:
        counts[table]=db.scalar(text(f"SELECT count(*) FROM {table} WHERE status='running' AND {column}>now()-interval '30 minutes'"))
    counts['release_monitor_jobs']=db.scalar(text("SELECT count(*) FROM release_monitor_jobs WHERE status='running' AND lease_until>now()"))
    counts['active_research_queries']=db.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state IN ('active','idle in transaction') AND (query ILIKE '%observations%' OR query ILIKE '%fomc_%')"))
print(counts)
raise SystemExit(1 if any(counts.values()) else 0)

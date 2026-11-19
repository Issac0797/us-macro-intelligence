"""Rollback only an isolated schema; never downgrade application tables."""
import os
import subprocess
import sys
import uuid
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect, text


@pytest.mark.parametrize('dialect',['sqlite','postgres'] if os.getenv('TEST_DATABASE_URL') else ['sqlite'])
def test_chart_workspace_migration_and_rollback_preserves_history(tmp_path,dialect):
    schema=None;admin=None
    env=os.environ.copy();env['MONITOR_ENABLED']='false'
    if dialect=='postgres':
        url=os.environ['TEST_DATABASE_URL'];schema='migration_'+uuid.uuid4().hex
        admin=create_engine(url)
        with admin.begin() as c:c.execute(text(f'CREATE SCHEMA "{schema}"'))
        env['PGOPTIONS']='-csearch_path='+schema
        engine=create_engine(url,connect_args={'options':'-csearch_path='+schema})
    else:
        url='sqlite:///'+(tmp_path/'workspaces.db').as_posix();engine=create_engine(url)
    env['DATABASE_URL']=url
    def migrate(*args):
        subprocess.run([sys.executable,'-m','alembic',*args],cwd=Path(__file__).resolve().parents[1],env=env,check=True,capture_output=True,timeout=40)
    try:
        migrate('upgrade','0003')
        with engine.begin() as c:
            c.execute(text("INSERT INTO series (id,short_name,title,category,frequency,units,unit_kind,seasonal_adjustment,agency,default_transform,source,source_url) VALUES ('PAYEMS','Payroll','Payroll','labor','monthly','Thousands','level','SA','BLS','raw','FRED','https://fred.stlouisfed.org/series/PAYEMS')"))
            c.execute(text("INSERT INTO observations (series_id,observation_date,value,raw_value,units,source,source_url,version,collected_at) VALUES ('PAYEMS','2020-01-01',100,'100','Thousands','FRED','https://fred.stlouisfed.org/series/PAYEMS','fixture','2020-02-01')"))
            c.execute(text("INSERT INTO vintage_observations (series_id,observation_date,vintage_date,realtime_end,value,raw_value,retrieved_at,source) VALUES ('PAYEMS','2020-01-01','2020-02-01','2020-12-31',99,'99','2026-01-01','ALFRED')"))
        migrate('upgrade','head');assert 'chart_workspaces' in inspect(engine).get_table_names()
        if dialect=='postgres':
            with engine.connect() as c:assert c.scalar(text("SELECT data_type FROM information_schema.columns WHERE table_schema=:s AND table_name='chart_workspaces' AND column_name='configuration'"),{'s':schema})=='jsonb'
        migrate('downgrade','0003');assert 'chart_workspaces' not in inspect(engine).get_table_names()
        migrate('upgrade','head')
        with engine.connect() as c:
            assert c.scalar(text('SELECT value FROM observations'))==100
            assert c.scalar(text('SELECT value FROM vintage_observations'))==99
    finally:
        engine.dispose()
        if admin:
            with admin.begin() as c:c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()

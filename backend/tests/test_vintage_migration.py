import os,subprocess,sys
from pathlib import Path
from sqlalchemy import create_engine,text,inspect

def test_migration_roundtrip_preserves_original_observation(tmp_path):
    url='sqlite:///'+(tmp_path/'migration.db').as_posix()
    env=os.environ.copy();env['DATABASE_URL']=url;env['MONITOR_ENABLED']='false'
    backend=Path(__file__).resolve().parents[1]
    def migrate(*args):
        subprocess.run([sys.executable,'-m','alembic',*args],cwd=backend,env=env,check=True,capture_output=True,timeout=40)
    migrate('upgrade','0002')
    engine=create_engine(url)
    with engine.begin() as c:
        c.execute(text("INSERT INTO series (id,short_name,title,category,frequency,units,unit_kind,seasonal_adjustment,agency,default_transform,source,source_url) VALUES ('PAYEMS','Payroll','Payroll','labor','monthly','Thousands','level','SA','BLS','raw','FRED','https://fred.stlouisfed.org/series/PAYEMS')"))
        c.execute(text("INSERT INTO observations (series_id,observation_date,value,raw_value,units,source,source_url,version,collected_at) VALUES ('PAYEMS','2020-01-01',100,'100','Thousands','FRED','https://fred.stlouisfed.org/series/PAYEMS','fixture','2020-02-01')"))
    migrate('upgrade','head');assert 'vintage_observations' in inspect(engine).get_table_names()
    migrate('downgrade','0002');assert 'vintage_observations' not in inspect(engine).get_table_names()
    with engine.connect() as c:assert c.scalar(text('SELECT value FROM observations'))==100
    migrate('upgrade','head')
    with engine.connect() as c:assert c.scalar(text('SELECT count(*) FROM observations'))==1
    engine.dispose()

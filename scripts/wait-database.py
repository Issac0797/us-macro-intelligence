"""Wait for SQL readiness, not merely an open TCP port (crash recovery can lag)."""
import time
from sqlalchemy import create_engine,text
from app.config import get_settings

url=get_settings().database_url
engine=create_engine(url,connect_args={'connect_timeout':2} if url.startswith('postgresql') else {})
deadline=time.monotonic()+60
try:
    while True:
        try:
            with engine.connect() as connection: connection.execute(text('SELECT 1'))
            print('Database SQL readiness: OK')
            break
        except Exception:
            if time.monotonic()>=deadline:
                raise SystemExit('Database not ready after 60 seconds; inspect logs/postgres.stderr.log') from None
            time.sleep(1)
finally:
    engine.dispose()

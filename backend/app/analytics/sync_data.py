import logging
from app.db import SessionLocal
from app.models import Series
from app.sync import insert_statement,sync_series
from app.providers import get_provider
from app.config import get_settings

def main():
 logging.getLogger('httpx').setLevel(logging.WARNING)
 p=get_provider(get_settings())
 try:
  with SessionLocal() as db:
   for sid,title,freq,units,kind in [('ICSA','Initial Claims','weekly','Number','level'),('SAHMCURRENT','Sahm Rule Current','monthly','Percentage Points','rate'),('SAHMREALTIME','Real-time Sahm Rule','monthly','Percentage Points','rate')]:
    db.execute(insert_statement(db,Series).values(id=sid,short_name=title,title=title,category='labor',frequency=freq,units=units,unit_kind=kind,seasonal_adjustment='SA' if sid=='ICSA' else 'NSA',agency='U.S. Department of Labor' if sid=='ICSA' else 'Sahm / FRED',default_transform='raw',source='FRED',source_url=f'https://fred.stlouisfed.org/series/{sid}').on_conflict_do_nothing(index_elements=['id']));db.commit();sync_series(db,p,sid)
 finally:p.close()
if __name__=='__main__':main()

"""Treasury observations and same-date spreads; not a vintage availability claim."""
import argparse
import logging
from datetime import date, timedelta
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Series
from app.sync import insert_statement, latest_observations, sync_series, seed_catalog
from app.db import SessionLocal
from app.providers import get_provider
from app.config import get_settings
from app.release_service import aware

MATURITIES = [('DGS1MO','1M',1/12),('DGS3MO','3M',.25),('DGS6MO','6M',.5),('DGS1','1Y',1),('DGS2','2Y',2),('DGS3','3Y',3),('DGS5','5Y',5),('DGS7','7Y',7),('DGS10','10Y',10),('DGS20','20Y',20),('DGS30','30Y',30)]
SPREADS = {'10Y-2Y': ('DGS10','DGS2'), '10Y-3M': ('DGS10','DGS3MO'), '30Y-5Y': ('DGS30','DGS5')}
NOTE = 'Historical observation dates use latest stored FRED values, not verified ALFRED point-in-time availability. No interpolation or cross-date subtraction.'


def seed_treasury(db):
    for sid,label,years in MATURITIES:
        item=dict(id=sid,short_name=f'{label} Treasury',title=f'{label} Treasury Constant Maturity Rate',category='interest_rates',frequency='daily',units='Percent',unit_kind='rate',seasonal_adjustment='NSA',agency='Federal Reserve Board',default_transform='raw')
        db.execute(insert_statement(db,Series).values(**item,source='FRED',source_url=f'https://fred.stlouisfed.org/series/{sid}').on_conflict_do_nothing(index_elements=['id']))
    for sid,title,frequency,units,kind in [('USREC','NBER based Recession Indicators for the United States','monthly','Binary recession indicator','indicator'),('T10Y2Y','10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity','daily','Percent','rate')]:
        db.execute(insert_statement(db,Series).values(id=sid,short_name=title[:90],title=title,category='financial_conditions',frequency=frequency,units=units,unit_kind=kind,seasonal_adjustment='NSA',agency='Federal Reserve Bank of St. Louis',default_transform='raw',source='FRED',source_url=f'https://fred.stlouisfed.org/series/{sid}').on_conflict_do_nothing(index_elements=['id']))
    db.commit()


def histories(db, ids, start=None, end=None):
    result = {}
    for sid in ids:
        from app.read_queries import observation_rows
        result[sid] = {r.observation_date:r for r in db.execute(observation_rows(db,sid,start=start,end=min(end or date.today(),date.today())))}
    return result


def curve_at(data, requested, nearest=False):
    if requested>date.today(): raise HTTPException(422,'Curve observation date must not be in the future')
    used=requested
    if nearest:
        used=max((day for rows in data.values() for day,row in rows.items() if requested-timedelta(days=10)<=day<=requested and row.value is not None),default=None)
    points=[]
    for sid,label,years in MATURITIES:
        row=data[sid].get(used)
        points.append(dict(series_id=sid,maturity=label,maturity_years=years,value=float(row.value) if row and row.value is not None else None,
            observation_date=used if row else None,version=row.version if row else None,retrieved_at=aware(row.collected_at) if row else None,
            source_url=f'https://fred.stlouisfed.org/series/{sid}'))
    available=sum(p['value'] is not None for p in points)
    return dict(requested_date=requested,used_date=used if available else None,nearest_previous=nearest,available_maturities=available,points=points)


def yield_curves(db, dates, include_latest=True, nearest=False):
    if len(dates)>3: raise HTTPException(422,'At most three historical comparison dates')
    data=histories(db,[s[0] for s in MATURITIES])
    last=max((day for rows in data.values() for day,r in rows.items() if r.value is not None),default=None)
    curves=[]
    if include_latest and last: curves.append(dict(label='Latest stored',**curve_at(data,last)))
    curves += [dict(label=str(d),**curve_at(data,d,nearest)) for d in dates]
    return dict(units='Percent',latest_available_date=last,curves=curves,precision_note=NOTE,
        source='FRED / Federal Reserve H.15',maturities=[dict(series_id=sid,label=label,years=y) for sid,label,y in MATURITIES])


def spread_history(db,start,end):
    if start>end or (end-start).days>10958: raise HTTPException(422,'Spread range must be ordered and at most 30 years')
    data=histories(db,sorted({s for pair in SPREADS.values() for s in pair}),start,end);result=[]
    for name,(left,right) in SPREADS.items():
        dates=sorted(d for d in data[left].keys() | data[right].keys() if start<=d<=min(end,date.today()))
        points=[];inversions=[];active=None;last_negative=None
        for d in dates:
            a,b=data[left].get(d),data[right].get(d)
            value=float(a.value-b.value) if a and b and a.value is not None and b.value is not None else None
            points.append(dict(date=d,value=value,left_value=float(a.value) if a and a.value is not None else None,right_value=float(b.value) if b and b.value is not None else None,
                left_version=a.version if a else None,right_version=b.version if b else None))
            if value is not None and value<0:
                if active is None: active=d
                last_negative=d
            elif active is not None:
                inversions.append(dict(start=active,end=last_negative));active=None
        if active is not None: inversions.append(dict(start=active,end=last_negative))
        valid=[p for p in points if p['value'] is not None];current=valid[-1] if valid else None
        result.append(dict(name=name,units='Percentage points',points=points,current=current,
            percentile=100*sum(p['value']<=current['value'] for p in valid)/len(valid) if current else None,
            sample_count=len(valid),sample_start=valid[0]['date'] if valid else None,sample_end=valid[-1]['date'] if valid else None,inversion_intervals=inversions))
    if sum(len(s['points']) for s in result)>30000: raise HTTPException(422,'Spread query exceeds 30,000 points; shorten date range')
    return dict(spreads=result,precision_note=NOTE,percentile_note='Empirical percentile: share of valid selected-range observations <= current. Inversion runs contain observed negative spreads; missing observations break a run.')


def curve_changes(db,start,end,nearest=False):
    if start>end: raise HTTPException(422,'start must not exceed end')
    data=histories(db,[s[0] for s in MATURITIES]);a=curve_at(data,start,nearest);b=curve_at(data,end,nearest)
    return dict(start_curve=a,end_curve=b,precision_note=NOTE,changes=[dict(series_id=x['series_id'],maturity=x['maturity'],initial_yield=x['value'],final_yield=y['value'],change_bp=round((y['value']-x['value'])*100,10) if x['value'] is not None and y['value'] is not None else None) for x,y in zip(a['points'],b['points'])])


def main():
    p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');p.add_argument('--series',nargs='+');args=p.parse_args()
    logging.basicConfig(level=logging.INFO);logging.getLogger('httpx').setLevel(logging.WARNING)
    provider=get_provider(get_settings())
    try:
        failures=0
        with SessionLocal() as db:
            seed_catalog(db);seed_treasury(db)
            for sid in args.series or [s[0] for s in MATURITIES]+['USREC','T10Y2Y']:
                try:sync_series(db,provider,sid,full=args.full)
                except Exception:failures+=1
        if failures:raise SystemExit(1)
    finally:provider.close()


if __name__=='__main__':main()

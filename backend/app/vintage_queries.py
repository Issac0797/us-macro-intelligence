from collections import defaultdict
from datetime import date,timedelta
from types import SimpleNamespace
from statistics import mean
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Series
from app.vintage_models import VintageArchive,VintageObservation,VintageMetadata
from app.transforms import calculate,Transform,output_units,allowed_transforms
from app.alfred import SUPPORTED
from app.release_service import aware

PRECISION='Date-level ALFRED vintage; no intraday availability guarantee. Earliest archived value is not necessarily the official first release.'

def series_archive(db,sid):
    if sid not in SUPPORTED:raise HTTPException(404,'Unsupported ALFRED series')
    series=db.get(Series,sid);archive=db.get(VintageArchive,sid)
    if not series:raise HTTPException(404,'Unknown series')
    return series,archive

def historical_metadata(db,sid,at):
    return db.scalar(select(VintageMetadata).where(VintageMetadata.series_id==sid,VintageMetadata.realtime_start<=at,VintageMetadata.realtime_end>=at).order_by(VintageMetadata.realtime_start.desc()).limit(1))

def snapshot(db,sid,as_of,transform=Transform.RAW,start=None,end=None,window=3,frequency=None,page=1,page_size=500,compare_as_of=None):
    series,archive=series_archive(db,sid)
    if start and end and start>end:raise HTTPException(422,'start must not exceed end')
    result=dict(series_id=sid,as_of=as_of,precision='date',precision_note=PRECISION,source='ALFRED',source_url=f'https://alfred.stlouisfed.org/series?seid={sid}',page=page,page_size=page_size,count=0,observations=[],coverage='NOT_AVAILABLE',units=None,available_transforms=[])
    result['archive_first_vintage']=archive.first_vintage if archive else None
    result['archive_covered_through']=archive.covered_through if archive else None
    if not archive or archive.status!='complete' or not archive.first_vintage or as_of<archive.first_vintage or as_of>archive.covered_through:
        result['coverage_note']='Requested date is outside the verified archive. No current data substituted.';return result
    metadata=historical_metadata(db,sid,as_of)
    if not metadata:result['coverage_note']='Historical units metadata unavailable';return result
    if frequency and frequency!=metadata.frequency:raise HTTPException(422,'Only the native vintage frequency is supported; no silent resampling')
    spec=SimpleNamespace(unit_kind=series.unit_kind,frequency=metadata.frequency,units=metadata.units,seasonal_adjustment=metadata.seasonal_adjustment)
    q=select(VintageObservation).where(VintageObservation.series_id==sid,VintageObservation.vintage_date<=as_of,VintageObservation.realtime_end>=as_of,VintageObservation.observation_date<=as_of).order_by(VintageObservation.observation_date)
    rows=list(db.scalars(q))
    adapted=[SimpleNamespace(observation_date=r.observation_date,value=r.value,raw_value=r.raw_value,version=str(r.vintage_date),source='ALFRED',collected_at=aware(r.retrieved_at),released_at=None,realtime_start=r.vintage_date,realtime_end=r.realtime_end) for r in rows]
    try:points=calculate(spec,adapted,transform,window)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    points=[p for p in points if (not start or p['date']>=start) and (not end or p['date']<=end)]
    latest_at=compare_as_of or archive.covered_through
    if latest_at<archive.first_vintage or latest_at>archive.covered_through:raise HTTPException(422,'Comparison date is outside verified archive coverage')
    # Compute latest independently from its own vintage, never reuse future values as warm-up.
    latest_meta=historical_metadata(db,sid,latest_at)
    latest_points={};comparable=False
    if latest_meta:
        latest_spec=SimpleNamespace(unit_kind=series.unit_kind,frequency=latest_meta.frequency,units=latest_meta.units,seasonal_adjustment=latest_meta.seasonal_adjustment)
        comparable=output_units(spec,transform)==output_units(latest_spec,transform) and spec.frequency==latest_spec.frequency
        if comparable:
            latest_rows=list(db.scalars(select(VintageObservation).where(VintageObservation.series_id==sid,VintageObservation.vintage_date<=latest_at,VintageObservation.realtime_end>=latest_at,VintageObservation.observation_date<=latest_at).order_by(VintageObservation.observation_date)))
            latest_adapted=[SimpleNamespace(observation_date=r.observation_date,value=r.value,raw_value=r.raw_value,version=str(r.vintage_date),source='ALFRED',collected_at=r.retrieved_at,released_at=None,realtime_start=r.vintage_date,realtime_end=r.realtime_end) for r in latest_rows]
            latest_points={p['date']:p['value'] for p in calculate(latest_spec,latest_adapted,transform,window)}
    for point in points:
        point['realtime_end']=min(point['realtime_end'],as_of)
        value=latest_points.get(point['date']);point['vintage_date']=point['realtime_start'];point['latest_value']=value
        point['difference']=value-point['value'] if value is not None and point['value'] is not None else None
    result.update(coverage='AVAILABLE',units=output_units(spec,transform),native_units=metadata.units,frequency=metadata.frequency,available_transforms=allowed_transforms(spec),retrieved_at=aware(archive.retrieved_at),latest_as_of=latest_at,latest_comparable=comparable,count=len(points),observations=points[(page-1)*page_size:page*page_size])
    return result

def revision_amount(initial,revised,kind,units_match=True):
    if initial is None or revised is None or not units_match:return None,None
    delta=revised-initial
    percent=delta/abs(initial)*100 if initial!=0 and kind in ('index','level') else None
    return float(delta),float(percent) if percent is not None else None

def revision_data(db,sid,start=None,end=None,window_days=None,as_of=None):
    if window_days is not None and window_days not in (30,90,180):raise HTTPException(422,'window_days must be 30, 90 or 180')
    series,archive=series_archive(db,sid)
    if start and end and start>end:raise HTTPException(422,'start must not exceed end')
    if not archive or archive.status!='complete':return series,archive,[]
    analysis_end=as_of or archive.covered_through
    if analysis_end>archive.covered_through:raise HTTPException(422,'Analysis as_of date exceeds verified coverage')
    metadata=list(db.scalars(select(VintageMetadata).where(VintageMetadata.series_id==sid)))
    def units(at):return next((m.units for m in metadata if m.realtime_start<=at<=m.realtime_end),None)
    q=select(VintageObservation).where(VintageObservation.series_id==sid,VintageObservation.vintage_date<=analysis_end,VintageObservation.observation_date<=analysis_end)
    if start:q=q.where(VintageObservation.observation_date>=start)
    if end:q=q.where(VintageObservation.observation_date<=end)
    grouped=defaultdict(list)
    for r in db.scalars(q.order_by(VintageObservation.observation_date,VintageObservation.vintage_date)):grouped[r.observation_date].append(r)
    result=[]
    for period,rows in grouped.items():
        first=next((r for r in rows if r.value is not None),None)
        if not first:continue
        target=min(analysis_end,first.vintage_date+timedelta(days=window_days)) if window_days else analysis_end
        censored=window_days is not None and first.vintage_date+timedelta(days=window_days)>analysis_end
        last=next((r for r in reversed(rows) if r.vintage_date<=target<=r.realtime_end),None)
        initial_units=units(first.vintage_date);last_units=units(target)
        comparable=initial_units is not None and initial_units==last_units
        delta,percent=revision_amount(first.value,last.value if last else None,series.unit_kind,comparable and not censored)
        timeline=[];previous=None;previous_units=None
        for r in rows:
            native_units=units(r.vintage_date)
            step,_=revision_amount(previous.value if previous else None,r.value,series.unit_kind,native_units is not None and native_units==previous_units)
            timeline.append(dict(vintage_date=r.vintage_date,valid_through=min(r.realtime_end,analysis_end),value=float(r.value) if r.value is not None else None,raw_value=r.raw_value,units=native_units,step_revision=step,retrieved_at=aware(r.retrieved_at)))
            previous,previous_units=r,native_units
        result.append(dict(observation_date=period,first_available_vintage=first.vintage_date,initial_value=float(first.value),initial_units=initial_units,
            latest_available_vintage=last.vintage_date if last else None,revised_value=float(last.value) if last and last.value is not None else None,comparison_date=target,
            units=last_units,revision_units='Percentage points' if series.unit_kind=='rate' else last_units,absolute_revision=delta,percentage_revision=percent,
            comparable=comparable,censored=censored,timeline=timeline))
    return series,archive,result

def summary_statistics(rows):
    eligible=[r for r in rows if r['absolute_revision'] is not None and not r['censored']]
    def stats(sample):
        values=[r['absolute_revision'] for r in sample];n=len(values)
        return dict(sample_count=n,mean_revision=mean(values) if n else None,mean_absolute_revision=mean(abs(v) for v in values) if n else None,upward_ratio=sum(v>0 for v in values)/n if n else None,downward_ratio=sum(v<0 for v in values)/n if n else None,sample_start=min((r['observation_date'] for r in sample),default=None),sample_end=max((r['observation_date'] for r in sample),default=None))
    groups=defaultdict(list)
    for row in eligible:groups[row['revision_units']].append(row)
    by_units=[dict(units=unit,**stats(sample)) for unit,sample in groups.items()]
    years=defaultdict(list)
    for row in eligible:years[(row['observation_date'].year,row['revision_units'])].append(row)
    bins=[]
    for unit,sample in groups.items():
        values=[r['absolute_revision'] for r in sample];lo,hi=min(values),max(values);width=(hi-lo)/10 if hi>lo else 1
        counts=[0]*10
        for v in values:counts[min(9,int((v-lo)/width))]+=1
        bins.extend(dict(units=unit,lower=lo+i*width,upper=lo+(i+1)*width,count=n) for i,n in enumerate(counts))
    return dict(candidate_count=len(rows),sample_count=len(eligible),excluded_count=len(rows)-len(eligible),by_units=by_units,by_year=[dict(year=y,units=u,**stats(sample)) for (y,u),sample in sorted(years.items())],distribution=bins,note='Earliest available ALFRED vintage, not certified official initial release. Cross-unit comparisons and incomplete fixed windows excluded; historical patterns do not guarantee future revisions.')

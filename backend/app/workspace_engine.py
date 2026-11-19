"""Native transforms -> closed calendar buckets. Never fill across buckets."""
import calendar
import hashlib
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import select
from app.models import Series, Observation, utcnow
from app.sync import latest_observations
from app.transforms import Transform, calculate, output_units
from app.vintage_models import VintageArchive, VintageObservation
from app.vintage_queries import historical_metadata, PRECISION
from app.release_service import aware
from app.workspace_schemas import ChartConfiguration

RANK = {'daily': 0, 'weekly': 1, 'monthly': 2, 'quarterly': 3}
ALIGNMENT_NOTE = ('Native transforms precede alignment. Closed calendar periods only; weekly ends Sunday. '
    'Period end retains a missing final source record; average uses non-null records and reports missing counts; '
    'last available skips nulls within the same bucket only. No upsampling, cross-period fill or interpolation.')


def digest(value):
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def period_end(day, frequency):
    if frequency == 'daily': return day
    if frequency == 'weekly': return day + timedelta(days=6-day.weekday())
    month = day.month if frequency == 'monthly' else ((day.month-1)//3+1)*3
    return date(day.year, month, calendar.monthrange(day.year, month)[1])


def period_grid(start, end, frequency):
    current = period_end(start, frequency)
    result = []
    while current <= end:
        result.append(current)
        current = period_end(current+timedelta(days=1), frequency)
    return result


def native_history(db, sid, mode, as_of):
    from app.bounded_cache import native, dataset_version
    cutoff=as_of if mode=='vintage' else None
    return native.get(('native',sid,mode,cutoff,dataset_version(db)),lambda:_native_history(db,sid,mode,cutoff),ttl=30,copy=False)


def _native_history(db, sid, mode, as_of):
    series = db.get(Series, sid)
    if not series: raise HTTPException(404, f'Unknown database series: {sid}')
    if mode == 'vintage':
        archive = db.get(VintageArchive, sid)
        if not archive or archive.status != 'complete' or not archive.first_vintage or not (archive.first_vintage <= as_of <= archive.covered_through):
            message = (f'Historical Vintage Unavailable: selected {as_of}; archived coverage {archive.first_vintage} — {archive.covered_through}. No latest-data fallback.'
                       if archive and archive.first_vintage and archive.covered_through else 'Historical Vintage Unavailable; no latest-data fallback')
            return None, [], {'status': 'HISTORICAL_VINTAGE_UNAVAILABLE', 'message': message, 'series_id': sid,
                             'first_vintage': archive.first_vintage if archive else None, 'covered_through': archive.covered_through if archive else None}
        metadata = historical_metadata(db, sid, as_of)
        if not metadata:
            return None, [], {'status': 'HISTORICAL_VINTAGE_UNAVAILABLE', 'message': 'Historical unit metadata unavailable', 'series_id': sid}
        spec = SimpleNamespace(unit_kind=series.unit_kind, frequency=metadata.frequency, units=metadata.units, seasonal_adjustment=metadata.seasonal_adjustment)
        rows = list(db.scalars(select(VintageObservation).where(VintageObservation.series_id == sid,
            VintageObservation.vintage_date <= as_of, VintageObservation.realtime_end >= as_of,
            VintageObservation.observation_date <= as_of).order_by(VintageObservation.observation_date)))
        points = [dict(date=r.observation_date, value=r.value, raw_value=r.raw_value, version=str(r.vintage_date),
            vintage_date=r.vintage_date, collected_at=aware(r.retrieved_at), source='ALFRED', released_at=None,
            realtime_start=r.vintage_date, realtime_end=min(r.realtime_end, as_of)) for r in rows]
        info = dict(status='AVAILABLE', source='ALFRED', source_url=f'https://alfred.stlouisfed.org/series?seid={sid}',
            archive_fingerprint=archive.fingerprint, covered_through=archive.covered_through, retrieved_at=aware(archive.retrieved_at))
    else:
        spec = SimpleNamespace(unit_kind=series.unit_kind, frequency=series.frequency, units=series.units, seasonal_adjustment=series.seasonal_adjustment)
        from app.read_queries import observation_rows
        rows = db.execute(observation_rows(db, sid)).all()
        points = [dict(date=r.observation_date, value=r.value if r.units == series.units else None, raw_value=r.raw_value,
            version=r.version, vintage_date=None, collected_at=aware(r.collected_at), source=r.source,
            released_at=aware(r.released_at), realtime_start=r.realtime_start, realtime_end=r.realtime_end) for r in rows if r.observation_date <= date.today()]
        info = dict(status='AVAILABLE' if points else 'NEEDS_SYNC', source='FRED', source_url=series.source_url,
            retrieved_at=aware(series.last_synced_at), note='Dynamic latest stored data; historical observation dates do not imply verified historical availability.')
    info.update(series_id=sid, native_units=spec.units, native_frequency=spec.frequency, seasonal_adjustment=spec.seasonal_adjustment,
        latest_available_date=max((p['date'] for p in points if p['value'] is not None), default=None),
        dependency_fingerprint=digest([(p['date'], p['value'], p['version'], spec.units) for p in points]))
    return spec, points, info


def consecutive(sample, frequency):
    if frequency == 'daily': return True  # N source observations, not N calendar days.
    def number(d):
        if frequency == 'weekly': return d.toordinal()//7
        return d.year*12+d.month-1 if frequency == 'monthly' else d.year*4+(d.month-1)//3
    return all(number(b['date'])-number(a['date']) == 1 for a,b in zip(sample, sample[1:]))


def transform_points(spec, points, steps):
    spec = SimpleNamespace(**vars(spec))
    for step in steps:
        op = step.transform
        if op == 'raw': continue
        if op == 'absolute_change':
            points = [{**p, 'value': p['value']-points[i-1]['value'] if i and p['value'] is not None and points[i-1]['value'] is not None and consecutive(points[i-1:i+1], spec.frequency) else None} for i,p in enumerate(points)]
            if spec.unit_kind == 'rate': spec.units = 'Percentage points'
            continue
        if op in ('z_score', 'moving_average'):
            out = []
            for i, p in enumerate(points):
                sample = points[max(0, i-step.window+1):i+1]
                values = [q['value'] for q in sample]
                value = None
                if len(values) == step.window and all(v is not None for v in values) and consecutive(sample, spec.frequency):
                    avg = sum(values)/step.window
                    if op == 'moving_average': value = avg
                    else:
                        variance = sum((v-avg)**2 for v in values)/step.window
                        if variance > 0: value = (p['value']-avg)/variance.sqrt()
                out.append({**p, 'value': value})
            points = out
            if op == 'z_score': spec.units, spec.unit_kind = 'Z-score (rolling, ddof=0)', 'standardized'
        elif op == 'index_100':
            if spec.unit_kind not in ('index', 'level'): raise ValueError('Index 100 requires a level or index, not a rate or already normalized series')
            base = next((p['value'] for p in points if p['date'] == step.base_date), None)
            if base is None or base == 0: raise ValueError('Index 100 base date must contain a nonzero, available native observation')
            points = [{**p, 'value': p['value']/base*100 if p['value'] is not None and p['date'] >= step.base_date else None} for p in points]
            spec.units, spec.unit_kind = f'Index 100 ({step.base_date})', 'standardized'
        else:
            observations = [SimpleNamespace(observation_date=p['date'], **{k:p[k] for k in ('value','raw_value','version','source','collected_at','released_at','realtime_start','realtime_end')}) for p in points]
            converted = calculate(spec, observations, Transform(op))
            points = [{**p, 'value': Decimal(str(q['value'])) if q['value'] is not None else None} for p,q in zip(points, converted)]
            spec.units = output_units(spec, Transform(op))
            if op != 'absolute_change': spec.unit_kind = 'rate'
    return spec, points


def align_points(points, native, target, method, start, end):
    if RANK[target] < RANK[native]: raise ValueError(f'Cannot upsample {native} to {target}; select a common coarser frequency')
    if native == 'weekly' and target in ('monthly','quarterly'):
        raise ValueError('Weekly-to-calendar aggregation is ambiguous; use weekly data without implicit overlap allocation')
    buckets = defaultdict(list)
    for p in points:
        key = period_end(p['date'], target)
        if start <= key <= end: buckets[key].append(p)
    result = []
    for at in period_grid(start, end, target):
        rows = buckets.get(at, [])
        valid = [p for p in rows if p['value'] is not None]
        selected = rows[-1] if rows else None
        value = None
        if method == 'period_average': value = sum(p['value'] for p in valid)/len(valid) if valid else None
        else:
            if method == 'last_available': selected = valid[-1] if valid else None
            value = selected['value'] if selected else None
        result.append(dict(date=at, value=float(value) if value is not None else None,
            observation_dates=[p['date'] for p in rows], source_versions=sorted({p['version'] for p in rows}),
            effective_vintage=max((p['vintage_date'] for p in rows if p['vintage_date']), default=None),
            source_count=len(rows), valid_count=len(valid), missing_count=len(rows)-len(valid),
            selected_observation_date=selected['date'] if selected and method != 'period_average' else None))
    return result


def same_date_difference(left, right):
    other = {p['date']: p for p in right}
    result = []
    for p in left:
        q = other.get(p['date'])
        value = p['value']-q['value'] if q and p['value'] is not None and q['value'] is not None else None
        result.append({**p, 'value': value, 'version': digest([p['version'], q['version'] if q else None]),
            'vintage_date': max((d for d in (p['vintage_date'], q['vintage_date'] if q else None) if d), default=None)})
    return result


def recession_intervals(db, config, effective_end):
    if not config.show_recessions: return [], 'Disabled'
    # USREC historical observations do not establish historical availability.
    if config.data_mode == 'vintage': return [], 'Unavailable: no verified USREC vintage; latest shading not substituted'
    if not db.get(Series, 'USREC'): return [], 'USREC requires sync'
    rows = list(db.scalars(latest_observations(db, 'USREC')))
    intervals = []; active = None
    for r in rows:
        at = date(r.observation_date.year, r.observation_date.month, 1)
        if at > effective_end: break
        if r.value == 1:
            if active is None: active = at
        elif active is not None:
            if at >= config.start: intervals.append(dict(start=max(active, config.start), end=min(at, effective_end)))
            active = None
    if active is not None and active <= effective_end:
        intervals.append(dict(start=max(active, config.start), end=effective_end))
    return intervals, 'USREC / FRED monthly recession indicator; latest chronology, not an announcement-time signal'


def chart_data(db, config: ChartConfiguration):
    end = min(config.end, config.as_of if config.data_mode == 'vintage' else date.today())
    grid = period_grid(config.start, end, config.frequency)
    if len(grid)*len(config.lines) > 30000: raise HTTPException(422, 'Chart exceeds 30,000 points; shorten date range or choose a coarser frequency')
    cache = {}; output = []; axes = defaultdict(set); warnings = []
    def load(sid):
        if sid not in cache: cache[sid] = native_history(db, sid, config.data_mode, config.as_of)
        return cache[sid]
    for line in config.lines:
        spec, points, info = load(line.series_id)
        info = dict(info)
        if spec and line.subtract_series_id:
            right_spec, right, right_info = load(line.subtract_series_id)
            info['subtract'] = right_info
            if not right_spec or right_info['status'] != 'AVAILABLE':
                spec = None; info.update(status=right_info['status'], message=right_info.get('message','Subtraction series needs sync'))
            else:
                if spec.units != right_spec.units or spec.frequency != right_spec.frequency or spec.unit_kind != 'rate' or right_spec.unit_kind != 'rate':
                    raise HTTPException(422, 'Spreads require rate series with identical native units and frequency')
                points = same_date_difference(points, right)
                info['dependency_fingerprint'] = digest([info['dependency_fingerprint'], right_info['dependency_fingerprint']])
                spec = SimpleNamespace(**{**vars(spec), 'units': 'Percentage points'})
        saved_hash = config.data_fingerprints.get(line.key)
        if saved_hash and saved_hash != info.get('dependency_fingerprint'):
            warnings.append(f'{line.display_name}: source versions differ from the saved research fingerprint')
        values = []; units = None; transformed_points = []
        if spec:
            try:
                transformed, values = transform_points(spec, points, line.calculations)
                transformed_points = values
                units = transformed.units
                values = align_points(values, spec.frequency, config.frequency, line.alignment, config.start, end)
            except ValueError as exc: raise HTTPException(422, f'{line.display_name}: {exc}') from None
            if line.visible and any(p['value'] is not None for p in values): axes[line.axis].add(units)
        from app.availability import availability
        state = availability(points, transformed_points, values, source_status=info['status'], has_history=bool(points))
        output.append(dict(key=line.key, series_id=line.series_id, display_name=line.display_name, axis=line.axis,
            units=units, provenance=info, availability=state, missing_points=sum(p['value'] is None for p in values), points=values,
            calculation_note='Transforms run in order on native observations before alignment; rolling windows are backward-looking; z-score ddof=0'))
    if any(len(units)>1 for units in axes.values()):
        raise HTTPException(422, 'One axis contains incompatible units; assign the other axis or apply a common Z-score / Index 100 normalization')
    recessions, recession_note = recession_intervals(db, config, end)
    return dict(configuration=config.model_dump(mode='json'), generated_at=utcnow(), effective_end=end,
        mode_note='Dynamic latest stored data' if config.data_mode == 'latest' else PRECISION,
        alignment_note=ALIGNMENT_NOTE, dates=grid, series=output, axes={k:next(iter(v)) for k,v in axes.items()},
        warnings=warnings, recession_intervals=recessions, recession_note=recession_note)

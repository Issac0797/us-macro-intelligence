"""Bounded recent cards, preserving historical fallback and full transform warm-up."""
from datetime import date
from sqlalchemy import select
from app.models import Series, SyncTask, utcnow
from app.schemas import Card, Overview, SeriesOut
from app.transforms import Transform, calculate, allowed_transforms, output_units
from app.read_queries import observation_rows, warmup_count


def build_overview(db, category=None):
    query = select(Series).order_by(Series.id)
    if category:
        query = query.where(Series.category == category)
    cards = []
    for series in db.scalars(query):
        from app.diagnostics import checkpoint
        checkpoint()
        transform = Transform(series.default_transform)
        warm = warmup_count(series, transform)
        size = 36 + warm + 2
        while True:
            checkpoint()
            rows = db.execute(observation_rows(db, series.id, tail=size)).all()
            points = calculate(series, rows, transform)
            complete = len(rows) < size
            valid = [p for p in (points if complete else points[warm:]) if p['value'] is not None]
            if len(valid) >= 2 or complete:
                break
            # Rare long runs of missing values keep the original last-valid behavior.
            size *= 2
        latest = valid[-1] if valid else None
        previous = valid[-2] if len(valid) > 1 else None
        stale_days = {'daily': 7, 'weekly': 28, 'monthly': 75, 'quarterly': 150}[series.frequency]
        cards.append(Card(series=SeriesOut.model_validate(series).model_copy(update={'available_transforms': allowed_transforms(series)}),
            value=latest['value'] if latest else None, previous_value=previous['value'] if previous else None,
            change=latest['value']-previous['value'] if latest and previous else None,
            observation_date=latest['date'] if latest else None,
            latest_observation_date=rows[-1].observation_date if rows else None,
            collected_at=latest['collected_at'] if latest else None, provider=latest['source'] if latest else None,
            transform=transform, units=output_units(series, transform), history=points[-36:],
            stale=latest is None or (date.today()-latest['date']).days > stale_days))
    task = db.scalar(select(SyncTask).order_by(SyncTask.started_at.desc()).limit(1))
    populated = sum(c.value is not None for c in cards)
    return Overview(generated_at=utcnow(), cards=cards,
        latest_sync=dict(status=task.status, series_id=task.series_id, provider=task.provider, finished_at=task.finished_at) if task else None,
        data_status='ready' if populated and populated == len(cards) else 'partial' if populated else 'empty')

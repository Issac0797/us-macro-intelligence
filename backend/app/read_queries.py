"""Column-only, date-bounded immutable-revision reads (no Observation ORM entities)."""
from sqlalchemy import select, func
from app.models import Observation


def observation_rows(db, sid, *, start=None, end=None, as_of=None, tail=None, warmup=0):
    table = Observation.__table__
    filters = [table.c.series_id == sid]
    if as_of is not None:
        filters.append(table.c.collected_at <= as_of)
    if end is not None:
        filters.append(table.c.observation_date <= end)
    dates = select(table.c.observation_date).where(*filters).distinct()
    if tail is not None:
        dates = dates.order_by(table.c.observation_date.desc()).limit(tail)
        lower = select(func.min(dates.subquery().c.observation_date)).scalar_subquery()
        filters.append(table.c.observation_date >= lower)
    elif start is not None:
        if warmup:
            prior = dates.where(table.c.observation_date < start).order_by(table.c.observation_date.desc()).limit(warmup).subquery()
            lower = select(func.coalesce(func.min(prior.c.observation_date), start)).scalar_subquery()
            filters.append(table.c.observation_date >= lower)
        else:
            filters.append(table.c.observation_date >= start)
    ranked = select(*table.c, func.row_number().over(
        partition_by=table.c.observation_date,
        order_by=(table.c.collected_at.desc(), table.c.id.desc())).label('_rank')).where(*filters).subquery()
    return select(*(ranked.c[c.name] for c in table.c)).where(ranked.c._rank == 1).order_by(ranked.c.observation_date)


def warmup_count(series, transform, window=3):
    return {'raw': 0, 'mom': 1, 'yoy': 12 if series.frequency == 'monthly' else 4,
            'annualized_3m': 3 if series.frequency == 'monthly' else 1,
            'annualized_6m': 6 if series.frequency == 'monthly' else 2,
            'absolute_change': 1, 'moving_average': window - 1}[str(transform)]

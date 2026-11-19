"""Calendar-aligned transforms; never fill or interpolate missing observations."""
from datetime import date
from decimal import Decimal
from enum import StrEnum


class Transform(StrEnum):
    RAW = "raw"
    MOM = "mom"
    YOY = "yoy"
    ANNUALIZED_3M = "annualized_3m"
    ANNUALIZED_6M = "annualized_6m"
    MOVING_AVERAGE = "moving_average"
    ABSOLUTE_CHANGE = "absolute_change"


def validate_transform(series, transform: Transform, window: int = 3):
    if not 2 <= window <= 365:
        raise ValueError("Moving average window must be between 2 and 365 observations")
    if transform in (Transform.RAW, Transform.MOVING_AVERAGE, Transform.ABSOLUTE_CHANGE):
        return
    if series.unit_kind not in ("index", "level"):
        raise ValueError("Percentage growth transforms are not applicable to rate series; use absolute change (percentage points)")
    if series.frequency not in ("monthly", "quarterly"):
        raise ValueError("Growth transforms require monthly or quarterly native frequency")
    if transform == Transform.MOM and series.frequency != "monthly":
        raise ValueError("MoM requires monthly observations")
    if transform in (Transform.MOM, Transform.ANNUALIZED_3M, Transform.ANNUALIZED_6M) and series.seasonal_adjustment not in ("SA", "SAAR"):
        raise ValueError("Short-term growth requires seasonally adjusted data")


def allowed_transforms(series):
    result = []
    for transform in Transform:
        try:
            validate_transform(series, transform)
            result.append(transform.value)
        except ValueError:
            pass
    return result


def period_number(day: date, frequency: str):
    if frequency == "weekly":
        return day.toordinal() // 7
    return day.year * 12 + day.month - 1 if frequency == "monthly" else day.year * 4 + (day.month - 1) // 3


def calculate(series, observations, transform: Transform, window=3):
    validate_transform(series, transform, window)
    frequency = series.frequency
    values = {period_number(o.observation_date, frequency): o.value for o in observations} if frequency != "daily" else {}
    results = []
    for i, observation in enumerate(observations):
        value = observation.value
        current = period_number(observation.observation_date, frequency)
        def lag(n):
            return observations[i - n].value if frequency == "daily" and i >= n else values.get(current - n)
        result = value
        if transform == Transform.MOVING_AVERAGE:
            sample = [value] + [lag(n) for n in range(1, window)]
            result = sum(sample) / window if all(v is not None for v in sample) else None
        elif transform == Transform.ABSOLUTE_CHANGE:
            previous = lag(1)
            result = value - previous if value is not None and previous is not None else None
        elif transform != Transform.RAW:
            periods_per_year = 12 if frequency == "monthly" else 4
            n, exponent = {
                Transform.MOM: (1, 1), Transform.YOY: (periods_per_year, 1),
                Transform.ANNUALIZED_3M: (3 if frequency == "monthly" else 1, 4),
                Transform.ANNUALIZED_6M: (6 if frequency == "monthly" else 2, 2),
            }[transform]
            previous = lag(n)
            result = ((value / previous) ** exponent - 1) * 100 if value is not None and previous is not None and previous > 0 and value > 0 else None
        results.append(dict(date=observation.observation_date, value=float(result) if result is not None else None,
            raw_value=observation.raw_value, version=observation.version, source=observation.source,
            collected_at=observation.collected_at, released_at=observation.released_at,
            realtime_start=observation.realtime_start, realtime_end=observation.realtime_end))
    return results


def output_units(series, transform):
    if transform in (Transform.MOM, Transform.YOY, Transform.ANNUALIZED_3M, Transform.ANNUALIZED_6M):
        return "Percent"
    if transform == Transform.ABSOLUTE_CHANGE and series.unit_kind == "rate":
        return "Percentage points"
    return series.units

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.transforms import Transform, calculate, output_units


def series(**kwargs):
    return SimpleNamespace(**(dict(frequency="monthly", unit_kind="index", seasonal_adjustment="SA", units="Index") | kwargs))


def points(values, quarterly=False):
    return [SimpleNamespace(observation_date=date(2020 + i // (4 if quarterly else 12), (i % 4) * 3 + 1 if quarterly else i % 12 + 1, 1),
            value=Decimal(str(v)) if v is not None else None, raw_value=str(v), version="test", source="test",
            collected_at=None, released_at=None, realtime_start=None, realtime_end=None) for i, v in enumerate(values)]


def test_mom_yoy_annualized():
    data = points([100 * 1.01 ** i for i in range(14)])
    for transform, expected in [(Transform.MOM, 1), (Transform.YOY, (1.01 ** 12 - 1) * 100),
                                (Transform.ANNUALIZED_3M, (1.01 ** 12 - 1) * 100),
                                (Transform.ANNUALIZED_6M, (1.01 ** 12 - 1) * 100)]:
        assert calculate(series(), data, transform)[-1]["value"] == pytest.approx(expected)


def test_quarterly_annualization_and_yoy():
    data = points([100, 101, 102, 103, 104], quarterly=True)
    s = series(frequency="quarterly")
    assert calculate(s, data, Transform.ANNUALIZED_3M)[1]["value"] == pytest.approx((1.01 ** 4 - 1) * 100)
    assert calculate(s, data, Transform.ANNUALIZED_6M)[2]["value"] == pytest.approx((1.02 ** 2 - 1) * 100)
    assert calculate(s, data, Transform.YOY)[4]["value"] == pytest.approx(4)


def test_missing_period_does_not_bridge():
    data = points([100, None, 102, 103])
    assert calculate(series(), data, Transform.MOM)[2]["value"] is None
    del data[1]
    assert calculate(series(), data, Transform.MOM)[1]["value"] is None
    assert calculate(series(), data, Transform.MOVING_AVERAGE)[1]["value"] is None


def test_ma_absolute_change_zero_denominator():
    data = points([0, 10, 20])
    assert calculate(series(), data, Transform.MOM)[1]["value"] is None
    assert calculate(series(), data, Transform.MOVING_AVERAGE)[-1]["value"] == 10
    assert calculate(series(), data, Transform.ABSOLUTE_CHANGE)[-1]["value"] == 10
    assert output_units(series(unit_kind="rate"), Transform.ABSOLUTE_CHANGE) == "Percentage points"


@pytest.mark.parametrize("metadata,transform", [
    ({"unit_kind": "rate"}, Transform.YOY), ({"frequency": "daily"}, Transform.YOY),
    ({"frequency": "quarterly"}, Transform.MOM), ({"seasonal_adjustment": "NSA"}, Transform.ANNUALIZED_3M),
])
def test_inapplicable_transforms(metadata, transform):
    with pytest.raises(ValueError):
        calculate(series(**metadata), [], transform)

from datetime import date
from decimal import Decimal

from app.providers import Datum
from app.sync import sync_series
from test_sync import FakeProvider


def test_health_catalog_docs_and_empty_state(client):
    assert client.get("/api/v1/health").json()["data_status"] == "empty"
    assert len(client.get("/api/v1/series").json()) == 10
    assert len(client.get("/api/v1/series?category=inflation").json()) == 4
    assert client.get("/api/v1/overview").json()["data_status"] == "empty"
    assert client.get("/docs").status_code == 200
    assert "/api/v1/series/{series_id}/observations" in client.get("/openapi.json").json()["paths"]


def test_observations_real_route_and_provenance(client, db):
    sync_series(db, FakeProvider(), "CPIAUCSL")
    data = client.get("/api/v1/series/CPIAUCSL/observations").json()
    assert data["count"] == 2 and data["observations"][0]["value"] == 100
    assert data["observations"][1]["value"] is None
    assert data["observations"][0]["source"] == "fred_csv"
    assert data["observations"][0]["released_at"] is None
    assert client.get("/api/v1/series/CPIAUCSL/observations?limit=1&offset=1").json()["count"] == 2


def test_transform_warmup_before_range(client, db):
    provider = FakeProvider()
    provider.rows = [Datum(date(2023, 1, 1), Decimal("100"), "100"), Datum(date(2024, 1, 1), Decimal("105"), "105")]
    sync_series(db, provider, "CPIAUCSL")
    data = client.get("/api/v1/series/CPIAUCSL/observations?transform=yoy&start=2024-01-01").json()
    assert data["observations"][0]["value"] == 5
    overview = client.get("/api/v1/overview?category=inflation").json()
    assert overview["data_status"] == "partial"
    card = next(c for c in overview["cards"] if c["series"]["id"] == "CPIAUCSL")
    assert card["value"] == 5 and card["transform"] == "yoy"


def test_errors_are_explicit(client):
    assert client.get("/api/v1/series/UNKNOWN").status_code == 404
    for query in ["transform=yoy", "window=1", "transform=unknown", "start=2025-01-01&end=2024-01-01", "as_of=2024-01-01T00:00:00", "limit=0"]:
        assert client.get("/api/v1/series/DFF/observations?" + query).status_code == 422
    detail = client.get("/api/v1/series/DFF").json()
    assert detail["available_transforms"] == ["raw", "moving_average", "absolute_change"]

"""Verify real FRED -> PostgreSQL -> FastAPI -> Next.js HTTP proxy; no fixtures."""
import argparse
import json
from datetime import date, timedelta

import httpx
from sqlalchemy import select, func

from app.config import get_settings
from app.db import SessionLocal
from app.models import Observation, Series
from app.providers import get_provider
from app.sync import latest_observations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    args = parser.parse_args()
    provider = get_provider(get_settings())
    results = []
    try:
        with SessionLocal() as db, httpx.Client(base_url=args.base_url, timeout=60, trust_env=False) as web:
            assert web.get("/api/v1/health").json()["database"] == "connected"
            overview = web.get("/api/v1/overview").json()
            assert overview["data_status"] == "ready", overview["data_status"]
            for series in db.scalars(select(Series).order_by(Series.id)):
                observations = list(db.scalars(latest_observations(db, series.id)))
                assert observations, series.id
                start = observations[-1].observation_date - timedelta(days=40 if series.frequency == "daily" else 400)
                reference = provider.observations(series.id, start, date.today())
                stored = {o.observation_date: o for o in observations}
                matches = 0
                for row in reference:
                    assert row.observation_date in stored, f"Missing stored date: {series.id}"
                    point = stored[row.observation_date]
                    assert point.value == row.value, f"FRED/DB mismatch: {series.id} {row.observation_date}"
                    assert point.source == provider.name and point.released_at is None
                    matches += 1
                response = web.get(f"/api/v1/series/{series.id}/observations", params={"start": start.isoformat(), "transform": "raw"})
                assert response.status_code == 200, series.id
                payload = response.json()
                for point in payload["observations"]:
                    expected = stored[date.fromisoformat(point["date"])].value
                    assert point["value"] == (float(expected) if expected is not None else None)
                assert matches > 0, series.id
                results.append({"id": series.id, "stored_dates": len(observations), "reference_matches": matches,
                                "latest_observation": str(observations[-1].observation_date)})
            for category in ("inflation", "labor", "growth", "monetary"):
                assert web.get("/api/v1/overview", params={"category": category}).json()["data_status"] == "ready"
            for route in ("/", "/inflation", "/labor", "/growth", "/monetary"):
                assert web.get(route).status_code == 200, route
            print(json.dumps({"status": "passed", "provider": provider.name, "series": results,
                              "observation_versions": db.scalar(select(func.count()).select_from(Observation))}, indent=2))
    finally:
        provider.close()


if __name__ == "__main__":
    main()

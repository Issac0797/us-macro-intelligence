"""Independent, injectable FRED transports. Never log request URLs (API keys)."""
import csv
import io
import logging
import random
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime

import httpx

from app.config import Settings

log = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code=status_code


@dataclass(frozen=True)
class Datum:
    observation_date: date
    value: Decimal | None
    raw_value: str
    realtime_start: date | None = None
    realtime_end: date | None = None


def parse_value(raw: str) -> Decimal | None:
    if raw in (".", "", "NA", "NaN"):
        return None
    try:
        value = Decimal(raw)
        if not value.is_finite():
            raise InvalidOperation
        return value
    except InvalidOperation:
        raise ProviderError("Invalid numeric value in FRED response") from None


def parse_observations(payload: dict) -> list[Datum]:
    try:
        return [Datum(date.fromisoformat(row["date"]), parse_value(row["value"]), row["value"],
                      date.fromisoformat(row["realtime_start"]), date.fromisoformat(row["realtime_end"]))
                for row in payload["observations"]]
    except (KeyError, ValueError, TypeError):
        raise ProviderError("Malformed FRED observations response") from None


class FredTransport:
    def __init__(self, settings: Settings, client=None, sleep=time.sleep, clock=time.monotonic):
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.fred_timeout_seconds, follow_redirects=True)
        self.sleep, self.clock = sleep, clock
        self.last_request = float("-inf")

    def close(self):
        self.client.close()

    def request(self, url: str, params: dict):
        for attempt in range(self.settings.fred_max_retries + 1):
            self.sleep(max(0, 60 / self.settings.fred_requests_per_minute - (self.clock() - self.last_request)))
            self.last_request = self.clock()
            response = None
            try:
                response = self.client.get(url, params=params)
                if response.status_code == 200:
                    return response
                if response.status_code != 429 and response.status_code < 500:
                    raise ProviderError(f"FRED rejected request (HTTP {response.status_code})",response.status_code)
                reason = f"HTTP {response.status_code}"
            except (httpx.TimeoutException, httpx.TransportError):
                reason = "timeout or network error"
            if attempt == self.settings.fred_max_retries:
                raise ProviderError(f"FRED request exhausted retries: {reason}") from None
            delay = min(60, 2 ** attempt + random.random())
            if response is not None and response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = min(120, max(delay, float(retry_after)))
                except ValueError:
                    try:
                        delay = min(120, max(delay, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()))
                    except (ValueError, TypeError):
                        pass
            log.warning("FRED retry attempt=%s reason=%s delay=%.1fs", attempt + 1, reason, delay)
            self.sleep(delay)


class FredAPIProvider(FredTransport):
    name = "fred_api"

    def __init__(self, settings: Settings, **kwargs):
        if not settings.fred_api_key.get_secret_value():
            raise ProviderError("FRED_API_KEY is required for fred_api")
        super().__init__(settings, **kwargs)

    def json(self, endpoint: str, params: dict):
        response = self.request(f"https://api.stlouisfed.org/fred/{endpoint}", {
            **params, "api_key": self.settings.fred_api_key.get_secret_value(), "file_type": "json",
        })
        try:
            payload = response.json()
            if not isinstance(payload, dict) or "error_code" in payload:
                raise ValueError
            return payload
        except (ValueError, TypeError):
            raise ProviderError("Invalid JSON response from FRED") from None

    def metadata(self, series_id: str):
        try:
            row = self.json("series", {"series_id": series_id})["seriess"][0]
            return dict(title=row["title"], units=row["units"],
                        frequency={"M": "monthly", "Q": "quarterly", "D": "daily", "W": "weekly"}[row["frequency_short"]],
                        seasonal_adjustment=row["seasonal_adjustment_short"],
                        source_updated_at=datetime.fromisoformat(row["last_updated"]))
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("Malformed or unsupported FRED series metadata") from None

    def observations(self, series_id: str, start: date, end: date):
        offset, rows = 0, []
        # Current as-of snapshot, not a claim to reconstruct the full ALFRED archive.
        as_of = None
        while True:
            payload = self.json("series/observations", dict(series_id=series_id,
                observation_start=start.isoformat(), observation_end=end.isoformat(),
                units="lin", sort_order="asc", limit=100000, offset=offset,
                **({"realtime_start":as_of,"realtime_end":as_of} if as_of else {})))
            page = parse_observations(payload)
            if as_of is None:as_of=payload.get("realtime_start") or (str(page[0].realtime_start) if page and page[0].realtime_start else None)
            rows.extend(page)
            offset += len(page)
            if offset >= int(payload.get("count", offset)):
                return rows
            if not page:
                raise ProviderError("FRED pagination stalled")


class FredCSVProvider(FredTransport):
    """Explicit keyless import. CSV has no release timestamps or vintage metadata."""
    name = "fred_csv"

    def metadata(self, series_id: str):
        return {}  # Curated catalog; not represented as API-refreshed metadata.

    def observations(self, series_id: str, start: date, end: date):
        response = self.request("https://fred.stlouisfed.org/graph/fredgraph.csv", {
            "id": series_id, "cosd": start.isoformat(), "coed": end.isoformat(),
        })
        reader = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
        if not reader.fieldnames or series_id not in reader.fieldnames or "observation_date" not in reader.fieldnames:
            raise ProviderError("Malformed FRED CSV response")
        try:
            return [Datum(date.fromisoformat(row["observation_date"]), parse_value(row[series_id]), row[series_id])
                    for row in reader if start <= date.fromisoformat(row["observation_date"]) <= end]
        except (ValueError, KeyError, TypeError):
            raise ProviderError("Malformed FRED CSV observation") from None


def get_provider(settings: Settings):
    if settings.data_provider == "fred_api":
        return FredAPIProvider(settings)
    if settings.data_provider == "fred_csv":
        return FredCSVProvider(settings)
    raise ProviderError("DATA_PROVIDER must be fred_api or fred_csv")

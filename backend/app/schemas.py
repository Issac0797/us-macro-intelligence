from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    short_name: str
    title: str
    category: str
    frequency: str
    units: str
    unit_kind: str
    seasonal_adjustment: str
    agency: str
    default_transform: str
    source: str
    source_url: str
    source_updated_at: datetime | None
    last_synced_at: datetime | None
    available_transforms: list[str] = []


class Point(BaseModel):
    date: date
    value: float | None
    raw_value: str
    version: str
    source: str
    collected_at: datetime
    released_at: datetime | None
    realtime_start: date | None
    realtime_end: date | None


class ObservationResponse(BaseModel):
    series: SeriesOut
    transform: str
    units: str
    window: int | None
    count: int
    offset: int
    limit: int
    observations: list[Point]
    availability: dict = {}
    vintage_scope: str = "Locally collected revisions only; not a complete ALFRED archive"


class Card(BaseModel):
    series: SeriesOut
    value: float | None
    previous_value: float | None
    change: float | None
    observation_date: date | None
    latest_observation_date: date | None
    collected_at: datetime | None
    provider: str | None
    transform: str
    units: str
    stale: bool
    history: list[Point]


class Overview(BaseModel):
    generated_at: datetime
    cards: list[Card]
    latest_sync: dict | None
    data_status: Literal["empty", "partial", "ready"]

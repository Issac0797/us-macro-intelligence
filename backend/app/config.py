from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(Path(__file__).resolve().parents[2] / ".env"), ".env"),
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )
    database_url: str = "postgresql+psycopg://macro@localhost:5432/macro"
    fred_api_key: SecretStr = SecretStr("")
    data_provider: str = "fred_csv"
    sync_start_date: date = date(1947, 1, 1)
    sync_lookback_days: int = Field(400, ge=1)
    fred_timeout_seconds: float = Field(30, gt=0)
    fred_max_retries: int = Field(4, ge=0, le=8)
    fred_requests_per_minute: int = Field(60, ge=1, le=120)
    calendar_refresh_seconds: int = Field(21600, ge=300)
    diagnostics_enabled: bool = False
    monitor_enabled: bool = False
    monitor_far_seconds: int = Field(21600, ge=60)
    monitor_day_seconds: int = Field(1800, ge=60)
    monitor_near_seconds: int = Field(300, ge=60)
    monitor_lease_seconds: int = Field(1800, ge=300)
    monitor_delay_seconds: int = Field(3600, ge=300)
    monitor_expire_seconds: int = Field(604800, ge=3600)
    vintage_cache_seconds: int = Field(3600, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

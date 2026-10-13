"""Application settings, loaded from environment variables (and a local .env file).

Why: configuration lives in ONE place so no URL, password or tuning value is
scattered through the code. pydantic-settings validates values at startup, so a
bad setting fails loudly instead of causing a mysterious bug later.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SkyCast"
    app_version: str = "1.0.0"
    app_env: str = "development"  # "development" | "production"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./skycast.db"
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    openmeteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    openmeteo_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    openmeteo_api_key: str = ""

    http_connect_timeout: float = 5.0
    http_read_timeout: float = 10.0

    weather_cache_ttl_seconds: int = 600  # 10 minutes
    geocoding_cache_ttl_seconds: int = 86_400  # 24 hours
    stale_cache_max_age_seconds: int = 21_600  # serve labelled stale data up to 6 hours

    rate_limit_per_minute: int = Field(default=120, ge=1)
    max_request_body_bytes: int = 16_384
    max_favorites_per_client: int = 50
    slow_request_seconds: float = 1.0

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

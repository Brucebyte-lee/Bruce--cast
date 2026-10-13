"""Shared test fixtures. The real Open-Meteo API is NEVER called: httpx.MockTransport
intercepts every outgoing request and answers from FakeProvider."""

from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.deps import get_weather_service
from app.core.cache import TTLCache
from app.core.config import Settings, get_settings
from app.database.session import Base, get_db
from app.main import create_app
from app.services.weather import WeatherService


def make_forecast(
    tz: str = "Africa/Nairobi",
    current_time: str = "2026-10-12T14:15",
    start_date: str = "2026-10-12",
    offset: int = 10800,
    prob: dict[int, float] | None = None,
    drop_current: tuple[str, ...] = (),
    drop_hourly: tuple[str, ...] = (),
    drop_daily: tuple[str, ...] = (),
) -> dict:
    """Build an Open-Meteo style forecast payload (metric units)."""
    first = date.fromisoformat(start_date)
    days = [first + timedelta(days=i) for i in range(7)]
    hours = [f"{d.isoformat()}T{h:02d}:00" for d in days for h in range(24)]
    prob = prob or {}
    current = {
        "time": current_time, "interval": 900, "temperature_2m": 21.0, "relative_humidity_2m": 58,
        "apparent_temperature": 22.4, "is_day": 1, "precipitation": 0.0, "weather_code": 2,
        "pressure_msl": 1013.0, "wind_speed_10m": 18.0, "wind_direction_10m": 95, "wind_gusts_10m": 30.0,
    }  # fmt: skip
    hourly = {
        "time": hours,
        "temperature_2m": [15 + (i % 24) * 0.5 for i in range(len(hours))],
        "precipitation_probability": [prob.get(i, 0) for i in range(len(hours))],
        "weather_code": [2] * len(hours),
        "wind_speed_10m": [12.0] * len(hours),
        "is_day": [1 if 6 <= (i % 24) < 18 else 0 for i in range(len(hours))],
    }
    daily = {
        "time": [d.isoformat() for d in days],
        "weather_code": [2, 3, 61, 3, 1, 0, 2],
        "temperature_2m_max": [24.0, 25.0, 19.0, 23.0, 26.0, 27.0, 25.0],
        "temperature_2m_min": [14.0, 13.0, 12.0, 11.0, 10.0, 14.0, 15.0],
        "precipitation_sum": [0.0, 0.2, 8.5, 1.0, 0.0, 0.0, 0.4],
        "precipitation_probability_max": [10, 20, 80, 30, 5, 0, 15],
        "wind_speed_10m_max": [20.0] * 7,
        "uv_index_max": [9.0, 8.0, 4.0, 6.0, 9.0, 10.0, 8.0],
        "sunrise": [f"{d.isoformat()}T06:20" for d in days],
        "sunset": [f"{d.isoformat()}T18:30" for d in days],
    }
    for key in drop_current:
        current.pop(key)
    for key in drop_hourly:
        hourly.pop(key)
    for key in drop_daily:
        daily.pop(key)
    return {"latitude": -1.3, "longitude": 36.8, "timezone": tz, "utc_offset_seconds": offset,
            "current": current, "hourly": hourly, "daily": daily}  # fmt: skip


NAIROBI = {"id": 184745, "name": "Nairobi", "latitude": -1.28333, "longitude": 36.81667,
           "country": "Kenya", "country_code": "KE", "admin1": "Nairobi Area",
           "timezone": "Africa/Nairobi", "population": 4397073}  # fmt: skip
PARIS_FR = {"id": 2988507, "name": "Paris", "latitude": 48.85341, "longitude": 2.3488,
            "country": "France", "country_code": "FR", "admin1": "Île-de-France", "timezone": "Europe/Paris"}  # fmt: skip
PARIS_TX = {"id": 4717560, "name": "Paris", "latitude": 33.66094, "longitude": -95.55551,
            "country": "United States", "country_code": "US", "admin1": "Texas", "timezone": "America/Chicago"}  # fmt: skip


class FakeProvider:
    """Stands in for Open-Meteo. Tests change its attributes to simulate failures."""

    def __init__(self) -> None:
        self.forecast: dict = make_forecast()
        self.geocoding: dict = {"results": [NAIROBI]}
        self.forecast_status = 200
        self.forecast_text: str | None = None
        self.forecast_raise: Exception | None = None
        self.failing_latitudes: set[float] = set()
        self.calls: list[str] = []

    @property
    def forecast_calls(self) -> int:
        return sum("api.open-meteo.com" in c for c in self.calls)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if request.url.host.startswith("geocoding"):
            return httpx.Response(200, json=self.geocoding)
        if self.forecast_raise:
            raise self.forecast_raise
        if float(request.url.params.get("latitude", 0)) in self.failing_latitudes:
            return httpx.Response(500, json={})
        if self.forecast_text is not None:
            return httpx.Response(self.forecast_status, text=self.forecast_text)
        return httpx.Response(self.forecast_status, json=self.forecast)


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


def build_settings(**overrides) -> Settings:
    base = {"database_url": "sqlite://", "rate_limit_per_minute": 10_000, "openmeteo_api_key": ""}
    return Settings(_env_file=None, **{**base, **overrides})


def build_service(provider: FakeProvider, **overrides) -> WeatherService:
    http = httpx.AsyncClient(transport=httpx.MockTransport(provider.handler))
    return WeatherService(http, build_settings(**overrides), TTLCache())


@pytest.fixture
def make_client(provider):
    """Factory: make_client(**settings) -> TestClient wired to a fresh in-memory DB + fake provider."""
    created: list[TestClient] = []

    def factory(**overrides) -> TestClient:
        settings = build_settings(**overrides)
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

        def override_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        service = WeatherService(
            httpx.AsyncClient(transport=httpx.MockTransport(provider.handler)), settings, TTLCache()
        )
        application = create_app(settings)
        application.dependency_overrides[get_db] = override_db
        application.dependency_overrides[get_settings] = lambda: settings
        application.dependency_overrides[get_weather_service] = lambda: service
        client = TestClient(application)
        created.append(client)
        return client

    yield factory
    for c in created:
        c.close()


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()

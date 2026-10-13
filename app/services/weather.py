"""Weather service: talks to Open-Meteo, validates and normalises the response.

Everything provider-specific (URLs, parameter names, response layout, WMO codes) stays in
this file so the rest of the app, and the frontend, never depend on Open-Meteo directly.
"""

import asyncio
import logging
import re
from datetime import UTC, date, datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.core.cache import CacheResult, TTLCache
from app.core.config import Settings
from app.core.errors import (
    AppError,
    UpstreamBadResponse,
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.schemas.location import LocationOut
from app.schemas.weather import (
    AlertsInfo,
    CompareItem,
    CompareResponse,
    Condition,
    CurrentWeather,
    DailyEntry,
    DataMeta,
    HourlyEntry,
    LocationRef,
    UnitLabels,
    WeatherOverview,
)
from app.services.insights import DayPoint, HourPoint, build_insights
from app.services.units import Units, compass
from app.services.wmo import describe

logger = logging.getLogger(__name__)

ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
ATTRIBUTION_URL = "https://open-meteo.com/"
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_COORDS = re.compile(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")

CURRENT_VARS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,"
    "weather_code,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
)
HOURLY_VARS = "temperature_2m,precipitation_probability,weather_code,wind_speed_10m,is_day"
DAILY_VARS = (
    "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "precipitation_probability_max,wind_speed_10m_max,uv_index_max,sunrise,sunset"
)

NO_ALERTS = AlertsInfo(
    available=False,
    message=(
        "Official severe-weather alerts are not available from Open-Meteo. "
        "Check your national meteorological service for warnings."
    ),
)


class WeatherService:
    def __init__(self, http: httpx.AsyncClient, settings: Settings, cache: TTLCache) -> None:
        self._http = http
        self._settings = settings
        self._cache = cache

    # ------------------------------------------------------------------ HTTP layer
    async def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._settings.openmeteo_api_key:
            params = {**params, "apikey": self._settings.openmeteo_api_key}
        try:
            response = await self._http.get(url, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("provider timeout", extra={"url": url})
            raise UpstreamTimeout() from exc
        except httpx.RequestError as exc:  # DNS failure, refused connection, no network...
            logger.warning("provider unreachable", extra={"url": url, "error": type(exc).__name__})
            raise UpstreamUnavailable() from exc

        status = response.status_code
        if status == 429:
            logger.warning("provider rate limit", extra={"url": url})
            raise UpstreamRateLimited()
        if status >= 500:
            logger.warning("provider server error", extra={"url": url, "status": status})
            raise UpstreamUnavailable()
        if status != 200:
            logger.error("provider rejected request", extra={"url": url, "status": status})
            raise UpstreamBadResponse()
        try:
            data = response.json()
        except ValueError as exc:
            logger.error("provider returned malformed JSON", extra={"url": url})
            raise UpstreamBadResponse() from exc
        if not isinstance(data, dict):
            raise UpstreamBadResponse()
        return data

    # ------------------------------------------------------------------ location search
    async def search_locations(self, query: str, count: int = 8) -> list[LocationOut]:
        query = " ".join(query.split())
        coords = _COORDS.match(query)
        if coords:
            lat, lon = float(coords.group(1)), float(coords.group(2))
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return [LocationOut(name=f"{lat:.4f}, {lon:.4f}", latitude=lat, longitude=lon)]

        name, _, hint = query.partition(",")  # "Nairobi, Kenya" -> name + hint
        name, hint = name.strip(), hint.strip().lower()
        if len(name) < 2:
            return []
        fetch_count = 20 if hint else count
        key = f"geo:{name.lower()}:{fetch_count}"

        async def fetch() -> list[LocationOut]:
            data = await self._get_json(
                self._settings.openmeteo_geocoding_url,
                {"name": name, "count": fetch_count, "language": "en", "format": "json"},
            )
            return _parse_locations(data)

        result = await self._cache.get_or_fetch(
            key, self._settings.geocoding_cache_ttl_seconds, self._settings.stale_cache_max_age_seconds, fetch
        )
        places: list[LocationOut] = result.value
        if hint:
            places = [p for p in places if _matches_hint(p, hint)]
        return places[:count]

    # ------------------------------------------------------------------ forecast
    async def _forecast(self, latitude: float, longitude: float) -> CacheResult:
        key = f"forecast:{latitude:.2f}:{longitude:.2f}"
        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "current": CURRENT_VARS,
            "hourly": HOURLY_VARS,
            "daily": DAILY_VARS,
            "timezone": "auto",
            "forecast_days": 7,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }

        async def fetch() -> dict[str, Any]:
            data = await self._get_json(self._settings.openmeteo_forecast_url, params)
            _validate_forecast_shape(data)
            return data

        return await self._cache.get_or_fetch(
            key, self._settings.weather_cache_ttl_seconds, self._settings.stale_cache_max_age_seconds, fetch
        )

    async def get_overview(
        self,
        latitude: float,
        longitude: float,
        units: Units,
        name: str | None = None,
        country: str | None = None,
    ) -> WeatherOverview:
        cached = await self._forecast(latitude, longitude)
        try:
            return _normalise(cached, latitude, longitude, units, name, country)
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            logger.error("could not normalise provider data", extra={"error": repr(exc)})
            raise UpstreamBadResponse() from exc

    async def compare(self, locations: list, units: Units) -> CompareResponse:
        async def one(loc) -> CompareItem:
            ref = LocationRef(
                name=loc.name,
                country=loc.country,
                latitude=loc.latitude,
                longitude=loc.longitude,
                timezone=loc.timezone or "UTC",
            )
            try:
                overview = await self.get_overview(loc.latitude, loc.longitude, units, loc.name, loc.country)
            except AppError as exc:  # one failing city must not break the whole comparison
                return CompareItem(location=ref, error=exc.message)
            return CompareItem(
                location=overview.location,
                current=overview.current,
                today=overview.daily[0] if overview.daily else None,
                stale=overview.meta.stale,
            )

        items = await asyncio.gather(*(one(loc) for loc in locations))
        return CompareResponse(units=UnitLabels(**units.labels), items=list(items))

    async def provider_reachable(self) -> bool:
        try:
            await self._get_json(
                self._settings.openmeteo_geocoding_url, {"name": "Nairobi", "count": 1, "format": "json"}
            )
            return True
        except AppError:
            return False


# ---------------------------------------------------------------------- parsing helpers
def _parse_locations(data: dict[str, Any]) -> list[LocationOut]:
    raw = data.get("results")
    if raw is None:  # Open-Meteo omits "results" when nothing matches
        return []
    if not isinstance(raw, list):
        raise UpstreamBadResponse()
    places: list[LocationOut] = []
    for item in raw:
        try:
            places.append(
                LocationOut(
                    id=item.get("id"),
                    name=item["name"],
                    country=item.get("country"),
                    country_code=item.get("country_code"),
                    admin1=item.get("admin1"),
                    latitude=float(item["latitude"]),
                    longitude=float(item["longitude"]),
                    timezone=item.get("timezone"),
                    population=item.get("population"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue  # skip malformed entries instead of failing the whole search
    return places


def _matches_hint(place: LocationOut, hint: str) -> bool:
    haystack = [place.country, place.country_code, place.admin1]
    return any(h and hint in h.lower() for h in haystack)


def _validate_forecast_shape(data: dict[str, Any]) -> None:
    for section in ("current", "hourly", "daily"):
        if not isinstance(data.get(section), dict):
            raise UpstreamBadResponse()
    if not isinstance(data["current"].get("time"), str):
        raise UpstreamBadResponse()
    for section in ("hourly", "daily"):
        if not isinstance(data[section].get("time"), list) or not data[section]["time"]:
            raise UpstreamBadResponse()
    if not isinstance(data.get("timezone"), str):
        raise UpstreamBadResponse()


def _location_tz(data: dict[str, Any]) -> tzinfo:
    try:
        return ZoneInfo(data["timezone"])
    except (ZoneInfoNotFoundError, ValueError):
        return timezone(timedelta(seconds=int(data.get("utc_offset_seconds") or 0)))


def _column(block: dict[str, Any], key: str, length: int) -> list[Any]:
    """Return a data column, or a list of None when the provider did not send it."""
    values = block.get(key)
    return values if isinstance(values, list) and len(values) == length else [None] * length


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> bool | None:
    number = _num(value)
    return None if number is None else bool(number)


def _condition(code: Any) -> Condition:
    number = _num(code)
    code_int = int(number) if number is not None else None
    description, icon = describe(code_int)
    return Condition(code=code_int, description=description, icon=icon)


def _local(value: Any, tz: tzinfo) -> datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(value).replace(tzinfo=tz)


def _normalise(
    cached: CacheResult, latitude: float, longitude: float, units: Units, name: str | None, country: str | None
) -> WeatherOverview:
    data = cached.value
    tz = _location_tz(data)
    cur, hourly, daily = data["current"], data["hourly"], data["daily"]

    observed = _local(cur["time"], tz)
    assert observed is not None
    h_times = [_local(t, tz) for t in hourly["time"]]
    n_h = len(h_times)
    h_temp, h_prob = _column(hourly, "temperature_2m", n_h), _column(hourly, "precipitation_probability", n_h)
    h_code, h_wind, h_day = (_column(hourly, k, n_h) for k in ("weather_code", "wind_speed_10m", "is_day"))

    # Start the hourly window at the current hour (in the LOCATION's timezone), take 24 hours.
    current_hour = observed.replace(minute=0, second=0, microsecond=0)
    start = next((i for i, t in enumerate(h_times) if t is not None and t >= current_hour), 0)
    window = range(start, min(start + 24, n_h))

    d_dates = [date.fromisoformat(d) for d in daily["time"]]
    n_d = len(d_dates)
    d_cols = {k: _column(daily, k, n_d) for k in (
        "weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
        "precipitation_probability_max", "wind_speed_10m_max", "uv_index_max", "sunrise", "sunset")}  # fmt: skip

    hourly_out = [
        HourlyEntry(
            time=h_times[i], is_day=_flag(h_day[i]), condition=_condition(h_code[i]),
            temperature=units.temp(_num(h_temp[i])), precipitation_probability=_num(h_prob[i]),
            wind_speed=units.wind(_num(h_wind[i])),
        )
        for i in window if h_times[i] is not None
    ]  # fmt: skip
    daily_out = [
        DailyEntry(
            date=d_dates[i], weekday=_WEEKDAYS[d_dates[i].weekday()], condition=_condition(d_cols["weather_code"][i]),
            temp_min=units.temp(_num(d_cols["temperature_2m_min"][i])),
            temp_max=units.temp(_num(d_cols["temperature_2m_max"][i])),
            precipitation_sum=units.precip(_num(d_cols["precipitation_sum"][i])),
            precipitation_probability=_num(d_cols["precipitation_probability_max"][i]),
            wind_speed_max=units.wind(_num(d_cols["wind_speed_10m_max"][i])),
            uv_index_max=_num(d_cols["uv_index_max"][i]),
            sunrise=_local(d_cols["sunrise"][i], tz), sunset=_local(d_cols["sunset"][i], tz),
        )
        for i in range(n_d)
    ]  # fmt: skip

    today_idx = next((i for i, d in enumerate(d_dates) if d == observed.date()), 0)
    today = daily_out[today_idx]
    direction = _num(cur.get("wind_direction_10m"))
    current = CurrentWeather(
        observed_at=observed, is_day=_flag(cur.get("is_day")), condition=_condition(cur.get("weather_code")),
        temperature=units.temp(_num(cur.get("temperature_2m"))),
        feels_like=units.temp(_num(cur.get("apparent_temperature"))),
        humidity=_num(cur.get("relative_humidity_2m")),
        wind_speed=units.wind(_num(cur.get("wind_speed_10m"))),
        wind_gusts=units.wind(_num(cur.get("wind_gusts_10m"))),
        wind_direction_degrees=direction, wind_direction=compass(direction),
        precipitation=units.precip(_num(cur.get("precipitation"))),
        pressure=units.pressure(_num(cur.get("pressure_msl"))),
        uv_index=today.uv_index_max, temp_min=today.temp_min, temp_max=today.temp_max,
    )  # fmt: skip

    insights = build_insights(
        [HourPoint(h_times[i], _num(h_temp[i]), _num(h_prob[i]), _num(h_wind[i])) for i in window if h_times[i]],
        [DayPoint(d_dates[i], _num(d_cols["temperature_2m_max"][i]), _num(d_cols["temperature_2m_min"][i]),
                  _num(d_cols["precipitation_probability_max"][i]), _num(d_cols["uv_index_max"][i]))
         for i in range(today_idx, n_d)],
        units,
    )  # fmt: skip

    return WeatherOverview(
        location=LocationRef(name=name, country=country, latitude=latitude, longitude=longitude,
                             timezone=str(data["timezone"])),
        meta=DataMeta(provider="Open-Meteo", attribution=ATTRIBUTION, attribution_url=ATTRIBUTION_URL,
                      fetched_at=cached.fetched_at.astimezone(UTC), stale=cached.stale),
        units=UnitLabels(**units.labels), current=current, hourly=hourly_out, daily=daily_out,
        insights=insights, alerts=NO_ALERTS,
    )  # fmt: skip

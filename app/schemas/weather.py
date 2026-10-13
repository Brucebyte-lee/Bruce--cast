from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.location import LocationIn


class Condition(BaseModel):
    code: int | None
    description: str
    icon: str  # clear | partly | cloudy | fog | drizzle | rain | snow | thunder | unknown


class UnitLabels(BaseModel):
    temperature: str
    wind_speed: str
    precipitation: str
    pressure: str


class LocationRef(BaseModel):
    name: str | None
    country: str | None
    latitude: float
    longitude: float
    timezone: str


class DataMeta(BaseModel):
    provider: str
    attribution: str
    attribution_url: str
    fetched_at: datetime  # when WE retrieved it from the provider (UTC)
    stale: bool  # True = provider failed and this is older cached data


class CurrentWeather(BaseModel):
    observed_at: datetime  # provider's timestamp, in the location's timezone
    is_day: bool | None
    condition: Condition
    temperature: float | None
    feels_like: float | None
    humidity: float | None
    wind_speed: float | None
    wind_gusts: float | None
    wind_direction_degrees: float | None
    wind_direction: str | None
    precipitation: float | None
    pressure: float | None
    uv_index: float | None  # today's expected maximum
    temp_min: float | None  # today's range
    temp_max: float | None


class HourlyEntry(BaseModel):
    time: datetime
    is_day: bool | None
    condition: Condition
    temperature: float | None
    precipitation_probability: float | None
    wind_speed: float | None


class DailyEntry(BaseModel):
    date: date
    weekday: str
    condition: Condition
    temp_min: float | None
    temp_max: float | None
    precipitation_sum: float | None
    precipitation_probability: float | None
    wind_speed_max: float | None
    uv_index_max: float | None
    sunrise: datetime | None
    sunset: datetime | None


class Insight(BaseModel):
    type: str
    severity: str  # info | notice | warning
    message: str
    rule: str  # the plain-language rule that produced the message (transparency)


class AlertsInfo(BaseModel):
    available: bool
    provider: str | None = None
    message: str
    items: list[dict] = []


class WeatherOverview(BaseModel):
    location: LocationRef
    meta: DataMeta
    units: UnitLabels
    current: CurrentWeather
    hourly: list[HourlyEntry]
    daily: list[DailyEntry]
    insights: list[Insight]
    alerts: AlertsInfo


class CompareRequest(BaseModel):
    locations: list[LocationIn] = Field(min_length=2, max_length=5)


class CompareItem(BaseModel):
    location: LocationRef
    current: CurrentWeather | None = None
    today: DailyEntry | None = None
    stale: bool = False
    error: str | None = None


class CompareResponse(BaseModel):
    units: UnitLabels
    items: list[CompareItem]

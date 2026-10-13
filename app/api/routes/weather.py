from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_units, get_weather_service
from app.schemas.location import Latitude, Longitude
from app.schemas.weather import AlertsInfo, CompareRequest, CompareResponse, WeatherOverview
from app.services.units import Units
from app.services.weather import NO_ALERTS, WeatherService

router = APIRouter(prefix="/weather", tags=["weather"])

Service = Annotated[WeatherService, Depends(get_weather_service)]
UnitsDep = Annotated[Units, Depends(get_units)]
Lat = Annotated[Latitude, Query(description="Latitude, -90 to 90")]
Lon = Annotated[Longitude, Query(description="Longitude, -180 to 180")]
Name = Annotated[str | None, Query(max_length=100)]


async def _overview(service: WeatherService, lat: float, lon: float, units: Units, name, country):
    return await service.get_overview(lat, lon, units, name, country)


@router.get("/overview", response_model=WeatherOverview, summary="Everything the dashboard needs")
async def overview(service: Service, units: UnitsDep, latitude: Lat, longitude: Lon,
                   name: Name = None, country: Name = None):  # fmt: skip
    return await _overview(service, latitude, longitude, units, name, country)


@router.get(
    "/current",
    response_model=WeatherOverview,
    response_model_include={"location", "meta", "units", "current"},
    summary="Current conditions",
)
async def current(service: Service, units: UnitsDep, latitude: Lat, longitude: Lon,
                  name: Name = None, country: Name = None):  # fmt: skip
    return await _overview(service, latitude, longitude, units, name, country)


@router.get(
    "/hourly",
    response_model=WeatherOverview,
    response_model_include={"location", "meta", "units", "hourly"},
    summary="Next 24 hours",
)
async def hourly(service: Service, units: UnitsDep, latitude: Lat, longitude: Lon,
                 name: Name = None, country: Name = None):  # fmt: skip
    return await _overview(service, latitude, longitude, units, name, country)


@router.get(
    "/daily",
    response_model=WeatherOverview,
    response_model_include={"location", "meta", "units", "daily"},
    summary="Seven-day forecast",
)
async def daily(service: Service, units: UnitsDep, latitude: Lat, longitude: Lon,
                name: Name = None, country: Name = None):  # fmt: skip
    return await _overview(service, latitude, longitude, units, name, country)


@router.get("/alerts", response_model=AlertsInfo, summary="Weather alerts, when a provider supplies them")
async def alerts() -> AlertsInfo:
    return NO_ALERTS


@router.post("/compare", response_model=CompareResponse, summary="Compare 2-5 locations")
async def compare(service: Service, units: UnitsDep, body: CompareRequest) -> CompareResponse:
    return await service.compare(body.locations, units)

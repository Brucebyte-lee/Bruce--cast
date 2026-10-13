from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_weather_service
from app.schemas.location import LocationSearchResponse
from app.services.weather import WeatherService

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/search", response_model=LocationSearchResponse, summary="Search places by name or coordinates")
async def search_locations(
    service: Annotated[WeatherService, Depends(get_weather_service)],
    q: Annotated[str, Query(min_length=2, max_length=100, description='City, "City, Country" or "lat, lon"')],
    count: Annotated[int, Query(ge=1, le=10)] = 8,
) -> LocationSearchResponse:
    """Returns an empty `results` list (HTTP 200) when nothing matches."""
    return LocationSearchResponse(query=q, results=await service.search_locations(q, count))

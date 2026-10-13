"""FastAPI dependencies: small reusable pieces injected into route functions."""

import uuid
from typing import Annotated, Literal

from fastapi import Depends, Query, Request, Response

from app.core.config import Settings, get_settings
from app.services.units import Units
from app.services.weather import WeatherService

CLIENT_COOKIE = "skycast_client"


def get_weather_service(request: Request) -> WeatherService:
    return request.app.state.weather_service


def get_client_id(request: Request, response: Response, settings: Annotated[Settings, Depends(get_settings)]) -> str:
    """Identify an anonymous visitor with a random id kept in an httpOnly cookie.

    This scopes favorites and preferences to one browser without requiring accounts
    or collecting any personal data.
    """
    raw = request.cookies.get(CLIENT_COOKIE)
    try:
        return str(uuid.UUID(raw)) if raw else _issue(response, settings)
    except ValueError:
        return _issue(response, settings)


def _issue(response: Response, settings: Settings) -> str:
    client_id = str(uuid.uuid4())
    response.set_cookie(
        CLIENT_COOKIE, client_id, max_age=60 * 60 * 24 * 365, httponly=True,
        samesite="lax", secure=settings.is_production, path="/",
    )  # fmt: skip
    return client_id


def get_units(
    temperature_unit: Annotated[Literal["celsius", "fahrenheit"], Query()] = "celsius",
    unit_system: Annotated[Literal["metric", "imperial"], Query()] = "metric",
) -> Units:
    return Units(temperature=temperature_unit, system=unit_system)

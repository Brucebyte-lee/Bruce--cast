import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(value: str | None) -> str | None:
    """Strip control characters and extra whitespace from user supplied text."""
    if value is None:
        return None
    return " ".join(_CONTROL_CHARS.sub(" ", value).split()) or None


class LocationOut(BaseModel):
    """A place returned by city search."""

    id: int | None = None
    name: str
    country: str | None = None
    country_code: str | None = None
    admin1: str | None = None  # state / province / region
    latitude: float
    longitude: float
    timezone: str | None = None
    population: int | None = None


class LocationSearchResponse(BaseModel):
    query: str
    results: list[LocationOut]


class LocationIn(BaseModel):
    """A place sent by the client (favorites, compare)."""

    name: str = Field(min_length=1, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    latitude: Latitude
    longitude: Longitude
    timezone: str | None = Field(default=None, max_length=64)

    @field_validator("name", "country", "timezone", mode="before")
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return clean_text(value) if isinstance(value, str) else value

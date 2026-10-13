from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.location import LocationIn


class FavoriteCreate(LocationIn):
    pass


class FavoriteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str | None
    latitude: float
    longitude: float
    timezone: str | None
    position: int
    created_at: datetime


class FavoriteOrder(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=50)


class PreferencesIn(BaseModel):
    temperature_unit: Literal["celsius", "fahrenheit"] = "celsius"
    unit_system: Literal["metric", "imperial"] = "metric"
    theme: Literal["system", "light", "dark"] = "system"


class PreferencesOut(PreferencesIn):
    model_config = ConfigDict(from_attributes=True)

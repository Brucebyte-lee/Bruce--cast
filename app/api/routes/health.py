from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_weather_service
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.services.weather import WeatherService

router = APIRouter(tags=["health"])


@router.get("/health", summary="Application health (this app + its database)")
def health(db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]):
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - any DB failure means "degraded"
        database = "unavailable"
    body = {
        "status": "ok" if database == "ok" else "degraded",
        "version": settings.app_version,
        "environment": settings.app_env,
        "database": database,
    }
    return JSONResponse(body, status_code=200 if database == "ok" else 503)


@router.get("/health/providers", summary="External weather provider reachability")
async def provider_health(service: Annotated[WeatherService, Depends(get_weather_service)]):
    """Kept separate from /health so a provider outage never marks the app itself as down."""
    return {"open_meteo": "reachable" if await service.provider_reachable() else "unreachable"}

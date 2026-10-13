"""SkyCast application entry point: builds the FastAPI app and wires everything together."""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import favorites, health, locations, preferences, weather
from app.core.cache import TTLCache
from app.core.config import Settings, get_settings
from app.core.errors import AppError, error_body
from app.core.logging import configure_logging
from app.core.ratelimit import RateLimiter
from app.services.weather import WeatherService

logger = logging.getLogger("skycast")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

_HTTP_ERROR_CODES = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}
_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        timeout = httpx.Timeout(settings.http_read_timeout, connect=settings.http_connect_timeout)
        headers = {"User-Agent": f"SkyCast/{settings.app_version}"}
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            app.state.weather_service = WeatherService(client, settings, TTLCache())
            logger.info("application startup", extra={"env": settings.app_env, "version": settings.app_version})
            yield
        logger.info("application shutdown")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Weather forecasting API. Weather data by Open-Meteo.com (CC BY 4.0).",
        lifespan=lifespan,
    )
    limiter = RateLimiter(settings.rate_limit_per_minute)

    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"],
    )  # fmt: skip

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            length = request.headers.get("content-length", "")
            if length.isdigit() and int(length) > settings.max_request_body_bytes:
                return JSONResponse(error_body("payload_too_large", "The request body is too large."), status_code=413)
            wait = limiter.check(request.client.host if request.client else "unknown")
            if wait is not None:
                return JSONResponse(
                    error_body("rate_limited", "Too many requests. Please slow down."),
                    status_code=429, headers={"Retry-After": str(wait)},
                )  # fmt: skip
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        if elapsed > settings.slow_request_seconds:
            logger.warning("slow request", extra={"path": path, "seconds": round(elapsed, 2)})
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if not path.startswith(("/docs", "/redoc")):  # Swagger UI loads assets from a CDN
            response.headers["Content-Security-Policy"] = _CSP
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # ----- centralised error handling: every error uses the same JSON shape -----
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][0]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            error_body("validation_error", "Some request values are invalid.", details), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException):
        code = _HTTP_ERROR_CODES.get(exc.status_code, "http_error")
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(SQLAlchemyError)
    async def handle_db(_: Request, exc: SQLAlchemyError):
        logger.error("database error", exc_info=exc)
        return JSONResponse(
            error_body("database_unavailable", "Saved data is temporarily unavailable. Please try again."),
            status_code=503,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.error("unexpected error", exc_info=exc, extra={"path": request.url.path})
        return JSONResponse(error_body("internal_error", AppError.message), status_code=500)

    for module in (health, locations, weather, favorites, preferences):
        app.include_router(module.router, prefix="/api/v1")

    if FRONTEND_DIR.is_dir():  # mounted last so it never shadows API routes
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()

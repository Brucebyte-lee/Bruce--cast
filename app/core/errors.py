"""Application errors and the single JSON shape every error response uses.

Every error returned by the API looks like:
    {"error": {"code": "machine_readable_code", "message": "Human friendly text", "details": ...}}
so the frontend only needs ONE way to display errors.
"""

from typing import Any


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    message = "Something went wrong on our side. Please try again."

    def __init__(self, message: str | None = None, details: Any = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details


class UpstreamTimeout(AppError):
    status_code = 504
    code = "provider_timeout"
    message = "The weather service took too long to respond. Please try again."


class UpstreamUnavailable(AppError):
    status_code = 502
    code = "provider_unavailable"
    message = "The weather service is unreachable right now. Check your connection and try again."


class UpstreamRateLimited(AppError):
    status_code = 503
    code = "provider_rate_limited"
    message = "The weather service is receiving too many requests. Please wait a minute and retry."


class UpstreamBadResponse(AppError):
    status_code = 502
    code = "provider_bad_response"
    message = "The weather service returned data we could not understand."


class DuplicateFavorite(AppError):
    status_code = 409
    code = "duplicate_favorite"
    message = "This location is already in your favorites."


class FavoriteNotFound(AppError):
    status_code = 404
    code = "favorite_not_found"
    message = "That favorite does not exist."


class FavoriteLimitReached(AppError):
    status_code = 409
    code = "favorite_limit_reached"
    message = "You have reached the maximum number of favorites."


class InvalidOrder(AppError):
    status_code = 422
    code = "invalid_order"
    message = "The favorites order must list each of your favorites exactly once."


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}

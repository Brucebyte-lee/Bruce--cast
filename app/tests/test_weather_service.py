"""Service-level tests for caching behaviour (concurrency and stale fallback)."""

import asyncio

import httpx
import pytest

from app.core.errors import UpstreamTimeout
from app.services.units import Units
from app.tests.conftest import build_service


def test_simultaneous_identical_requests_make_one_provider_call(provider):
    service = build_service(provider)

    async def run():
        return await asyncio.gather(*(service.get_overview(-1.28, 36.81, Units()) for _ in range(5)))

    results = asyncio.run(run())
    assert len(results) == 5
    assert provider.forecast_calls == 1


def test_stale_data_is_served_and_labelled_when_provider_fails(provider):
    service = build_service(provider, weather_cache_ttl_seconds=0)  # every request wants fresh data

    async def run():
        fresh = await service.get_overview(-1.28, 36.81, Units())
        provider.forecast_raise = httpx.ConnectError("offline")
        stale = await service.get_overview(-1.28, 36.81, Units())
        return fresh, stale

    fresh, stale = asyncio.run(run())
    assert fresh.meta.stale is False and stale.meta.stale is True
    assert stale.meta.fetched_at == fresh.meta.fetched_at  # honest: the ORIGINAL retrieval time
    assert stale.current.temperature == fresh.current.temperature


def test_stale_data_is_not_served_once_too_old(provider):
    service = build_service(provider, weather_cache_ttl_seconds=0, stale_cache_max_age_seconds=0)

    async def run():
        await service.get_overview(-1.28, 36.81, Units())
        provider.forecast_raise = httpx.ReadTimeout("slow")
        await service.get_overview(-1.28, 36.81, Units())

    with pytest.raises(UpstreamTimeout):
        asyncio.run(run())


def test_error_with_no_cache_propagates(provider):
    provider.forecast_raise = httpx.ReadTimeout("slow")
    with pytest.raises(UpstreamTimeout):
        asyncio.run(build_service(provider).get_overview(1, 1, Units()))

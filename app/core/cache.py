"""A small in-memory TTL cache with request de-duplication and labelled stale fallback.

Why not Redis? One process, small data. Add Redis only when you run several
server instances that must share a cache.

Behaviour of get_or_fetch():
  * fresh entry in cache           -> returned immediately (stale=False)
  * two identical requests at once -> only ONE upstream call is made, both share it
  * upstream fails but an older entry exists (within max_stale_age) -> older entry is
    returned with stale=True so the UI can label it. Otherwise the error propagates.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.errors import AppError


@dataclass
class CacheResult:
    value: Any
    fetched_at: datetime  # when the data was really retrieved from the provider (UTC)
    stale: bool


@dataclass
class _Entry:
    value: Any
    fetched_at: datetime
    stored_monotonic: float


class TTLCache:
    def __init__(self, max_entries: int = 2000) -> None:
        self._entries: dict[str, _Entry] = {}
        self._inflight: dict[str, asyncio.Task] = {}
        self._max_entries = max_entries

    def clear(self) -> None:
        self._entries.clear()

    async def get_or_fetch(
        self,
        key: str,
        ttl: float,
        max_stale_age: float,
        fetcher: Callable[[], Awaitable[Any]],
    ) -> CacheResult:
        entry = self._entries.get(key)
        now = time.monotonic()
        if entry and now - entry.stored_monotonic < ttl:
            return CacheResult(entry.value, entry.fetched_at, stale=False)

        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(self._fetch_and_store(key, fetcher))
            self._inflight[key] = task
            task.add_done_callback(lambda _t, k=key: self._inflight.pop(k, None))

        try:
            return await asyncio.shield(task)
        except AppError:
            if entry and time.monotonic() - entry.stored_monotonic < max_stale_age:
                return CacheResult(entry.value, entry.fetched_at, stale=True)
            raise

    async def _fetch_and_store(self, key: str, fetcher: Callable[[], Awaitable[Any]]) -> CacheResult:
        value = await fetcher()
        fetched_at = datetime.now(UTC)
        if len(self._entries) >= self._max_entries:
            oldest = min(self._entries, key=lambda k: self._entries[k].stored_monotonic)
            del self._entries[oldest]
        self._entries[key] = _Entry(value, fetched_at, time.monotonic())
        return CacheResult(value, fetched_at, stale=False)

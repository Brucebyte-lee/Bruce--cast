"""Tiny per-IP sliding-window rate limiter (in memory, single process)."""

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> int | None:
        """Return None if the request is allowed, otherwise seconds to wait."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return max(1, int(self.window - (now - hits[0])))
        hits.append(now)
        if len(self._hits) > 10_000:  # prevent unbounded growth
            self._hits = defaultdict(deque, {k: v for k, v in self._hits.items() if v})
        return None

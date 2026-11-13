"""Sliding-window rate limiter for live Gemini calls (zero-bill protection).

Two budgets are enforced:

* **per IP** - ``LIVE_QUERIES_PER_IP_PER_DAY`` (default 10) live AI queries in
  any rolling 24 hours;
* **global** - ``GLOBAL_LIVE_QUERIES_PER_DAY`` across all callers, a hard
  ceiling on the total daily bill even under a distributed abuse attempt.

When either budget is spent the API does not fail - it falls back to the
deterministic insight engine and tells the UI why.

State is in-process memory. On serverless platforms each warm instance keeps
its own window, so the per-IP limit is a best-effort guard; swap the storage
for Redis / Upstash KV for a strictly global count.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from typing import Callable

from backend.config import (
    GLOBAL_LIVE_QUERIES_PER_DAY,
    LIVE_QUERIES_PER_IP_PER_DAY,
    RATE_LIMIT_WINDOW_SECONDS,
)

MAX_TRACKED_IPS = 10_000


class RateLimiter:
    def __init__(
        self,
        limit: int = LIVE_QUERIES_PER_IP_PER_DAY,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
        global_limit: int = GLOBAL_LIVE_QUERIES_PER_DAY,
        clock: Callable[[], float] = time.time,
    ):
        self.limit = limit
        self.window = window_seconds
        self.global_limit = global_limit
        self._clock = clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._global: deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self, bucket: deque[float], now: float) -> None:
        while bucket and now - bucket[0] >= self.window:
            bucket.popleft()

    def remaining(self, ip: str) -> int:
        with self._lock:
            now = self._clock()
            bucket = self._hits.get(ip)
            used = 0
            if bucket is not None:
                self._prune(bucket, now)
                used = len(bucket)
            self._prune(self._global, now)
            global_left = self.global_limit - len(self._global)
            return max(0, min(self.limit - used, global_left))

    def try_consume(self, ip: str) -> bool:
        """Record one live query for ``ip``. Returns False if over budget."""
        with self._lock:
            now = self._clock()
            self._prune(self._global, now)
            if len(self._global) >= self.global_limit:
                return False
            bucket = self._hits.get(ip)
            if bucket is None:
                if len(self._hits) >= MAX_TRACKED_IPS:
                    self._hits.popitem(last=False)
                bucket = deque()
                self._hits[ip] = bucket
            else:
                self._hits.move_to_end(ip)
            self._prune(bucket, now)
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            self._global.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._global.clear()

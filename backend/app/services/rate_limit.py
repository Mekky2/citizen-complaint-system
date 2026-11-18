"""Admission control for the public API.

Two independent limits:

* a sliding window per client (user id or IP) so one client cannot flood the service;
* a bounded number of in-flight requests so a burst degrades into a polite retry instead of
  queueing forever. Both are thread-safe and process-local; see the handoff notes for the
  multi-worker story.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(
        self,
        *,
        per_minute: int = 60,
        burst: int = 20,
        clock=time.monotonic,
    ):
        self.per_minute = max(1, per_minute)
        self.capacity = max(1, burst)
        self._window = 60.0
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._clock = clock
        self.rejected = 0

    def allow(self, client_id: str) -> tuple[bool, float]:
        """Return ``(allowed, retry_after_seconds)`` without ever raising."""
        now = self._clock()
        with self._lock:
            hits = self._hits.get(client_id)
            if hits is None:
                hits = deque()
                self._hits[client_id] = hits
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            limit = min(self.capacity, self.per_minute)
            if len(hits) >= limit:
                self.rejected += 1
                retry_after = max(1.0, self._window - (now - hits[0]))
                return False, round(retry_after, 1)
            hits.append(now)
            if len(self._hits) > 10_000:  # keep memory bounded under scanning traffic
                self._prune(now)
            return True, 0.0

    def _prune(self, now: float) -> None:
        stale = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] >= self._window
        ]
        for key in stale:
            self._hits.pop(key, None)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {"tracked_clients": len(self._hits), "rejected": self.rejected}


class ConcurrencyGate:
    """Bounded in-flight requests with a timeout for waiting callers."""

    def __init__(self, *, max_concurrent: int = 32):
        self.max_concurrent = max(1, max_concurrent)
        self._semaphore = threading.BoundedSemaphore(self.max_concurrent)
        self._lock = threading.Lock()
        self.rejected = 0

    def acquire(self, timeout: float) -> bool:
        acquired = self._semaphore.acquire(timeout=max(0.0, timeout))
        if not acquired:
            with self._lock:
                self.rejected += 1
        return acquired

    def release(self) -> None:
        try:
            self._semaphore.release()
        except ValueError:  # released more often than acquired; never crash a request
            pass

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "max_concurrent": self.max_concurrent,
                "rejected": self.rejected,
            }


__all__ = ["ConcurrencyGate", "SlidingWindowLimiter"]

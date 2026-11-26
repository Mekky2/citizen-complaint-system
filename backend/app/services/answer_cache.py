"""Small TTL/LRU cache for grounded RAG answers.

Only knowledge-base answers are cached: they do not depend on the user and contain no personal
data. The key is a hash of the normalized question, so the question text itself is not kept.
The cache is wiped automatically when the knowledge base is re-ingested.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from app.utils.arabic_normalizer import normalize_arabic


def cache_key(question: str) -> str:
    normalized = normalize_arabic(question or "", fold_taa_marbuta=True)
    normalized = " ".join(normalized.split()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class AnswerCache:
    def __init__(
        self,
        *,
        ttl_seconds: float = 300,
        max_entries: int = 500,
        version_provider: Callable[[], int] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self._version_provider = version_provider
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, int, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def _version(self) -> int:
        return int(self._version_provider()) if self._version_provider else 0

    def get(self, question: str) -> dict[str, Any] | None:
        version = self._version()
        key = cache_key(question)
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return None
            expires_at, entry_version, value = entry
            if expires_at <= now or entry_version != version:
                self._entries.pop(key, None)
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return dict(value)

    def set(self, question: str, value: dict[str, Any]) -> None:
        version = self._version()
        key = cache_key(question)
        expires_at = self._clock() + self.ttl_seconds
        with self._lock:
            self._entries[key] = (expires_at, version, dict(value))
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "hits": self.hits,
                "misses": self.misses,
                "max_entries": self.max_entries,
            }


__all__ = ["AnswerCache", "cache_key"]

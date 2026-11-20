"""Session storage with TTL, a size cap and one lock per session.

The in-memory implementation is the default for single-process development. It is behind a
small interface so a Redis or database implementation only has to provide ``get``/``clear`` and
can be selected by configuration, without touching the agents or the API.

Isolation: every session has its own lock, and the store never returns another session's
object. A long conversation is trimmed so one user cannot grow memory without bound.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

from app.agents.complaint_agent.conversation import ComplaintSession, new_session


class SessionStore(Protocol):
    def get(self, session_id: str) -> ComplaintSession: ...

    def lock(self, session_id: str): ...

    def clear(self) -> None: ...


class _Entry:
    __slots__ = ("session", "lock", "last_seen")

    def __init__(self, session: ComplaintSession):
        self.session = session
        self.lock = threading.RLock()
        self.last_seen = time.monotonic()


class InMemorySessionStore:
    """Thread-safe, TTL-bounded session store."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 1800,
        max_entries: int = 5000,
        max_history_messages: int = 40,
        max_turns: int = 6,
        clock=time.monotonic,
    ):
        self.ttl_seconds = max(0.0, ttl_seconds)
        self.max_entries = max(1, max_entries)
        self.max_history_messages = max(2, max_history_messages)
        self.max_turns = max(1, max_turns)
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()
        self._clock = clock
        self.evictions = 0

    def get(self, session_id: str) -> ComplaintSession:
        now = self._clock()
        with self._lock:
            self._sweep_locked(now)
            entry = self._entries.get(session_id)
            if entry is None:
                entry = _Entry(new_session(session_id, max_turns=self.max_turns))
                self._entries[session_id] = entry
                self._evict_locked()
            else:
                self._entries.move_to_end(session_id)
            entry.last_seen = now
            self._trim(entry.session)
            return entry.session

    @contextmanager
    def lock(self, session_id: str) -> Iterator[ComplaintSession]:
        """Serialise turns for one session without blocking other sessions."""
        session = self.get(session_id)
        with self._lock:
            entry = self._entries.get(session_id)
        if entry is None:  # evicted between get() and here (very unlikely)
            entry = _Entry(session)
        with entry.lock:
            yield entry.session

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {"sessions": len(self._entries), "evictions": self.evictions}

    # ----------------------------------------------------------------- helpers
    def _trim(self, session: ComplaintSession) -> None:
        if len(session.history) > self.max_history_messages:
            session.history = session.history[-self.max_history_messages :]

    def _sweep_locked(self, now: float) -> None:
        if self.ttl_seconds <= 0:
            return
        expired = [
            key for key, entry in self._entries.items() if now - entry.last_seen > self.ttl_seconds
        ]
        for key in expired:
            self._entries.pop(key, None)

    def _evict_locked(self) -> None:
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
            self.evictions += 1


__all__ = ["InMemorySessionStore", "SessionStore"]

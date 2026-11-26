"""Request tracing and structured logging without personal data.

Every API request gets a ``RequestTrace`` in a context variable. The gateway, cache and stores
write metadata into it (provider, latency, retries, token estimate, fallback reason) so the
endpoint can mark the response as degraded and log one structured line.

Nothing here accepts free text: callers pass counts, names and reason codes only. That keeps
phone numbers, national IDs and complaint text out of the logs.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("app.request")

_trace: ContextVar[RequestTrace | None] = ContextVar("request_trace", default=None)


@dataclass
class RequestTrace:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    started_at: float = field(default_factory=time.perf_counter)
    # Opaque user/session scope used only for per-user budgets. Never logged.
    user_id: str | None = field(default=None, repr=False)
    provider: str | None = None
    provider_calls: int = 0
    retries: int = 0
    tokens_estimate: int = 0
    cache_hit: bool = False
    degraded: bool = False
    fallback_reason: str | None = None

    def note_provider(self, name: str) -> None:
        self.provider = name
        self.provider_calls += 1

    def note_retry(self) -> None:
        self.retries += 1

    def note_tokens(self, tokens: int) -> None:
        if tokens > 0:
            self.tokens_estimate += tokens

    def degrade(self, reason: str) -> None:
        self.degraded = True
        if not self.fallback_reason:
            self.fallback_reason = reason

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.started_at) * 1000)

    def as_log(self, **extra: Any) -> dict[str, Any]:
        payload = {
            "request_id": self.request_id,
            "provider": self.provider,
            "latency_ms": self.elapsed_ms(),
            "provider_calls": self.provider_calls,
            "retries": self.retries,
            "tokens_estimate": self.tokens_estimate,
            "cache_hit": self.cache_hit,
            "degraded": self.degraded,
            "fallback_reason": self.fallback_reason,
        }
        payload.update(extra)
        return payload


def current_trace() -> RequestTrace | None:
    return _trace.get()


def start_trace() -> RequestTrace:
    trace = _trace.get()
    if trace is not None:
        return trace
    trace = RequestTrace()
    _trace.set(trace)
    return trace


def set_trace(trace: RequestTrace) -> None:
    _trace.set(trace)


def reset_trace() -> None:
    _trace.set(None)


def log_request(trace: RequestTrace, **extra: Any) -> None:
    """Emit one JSON line. Only metadata: never message text or identifiers."""
    logger.info(json.dumps(trace.as_log(**extra), ensure_ascii=False, default=str))

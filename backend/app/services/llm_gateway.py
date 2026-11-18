"""One LLM gateway used by every agent.

The gateway is the only place that knows about providers. Agents keep calling
``llm.complete(system, user)`` exactly as before; under that signature the gateway adds:

* a provider chain (primary Mistral/NIM -> optional secondary -> offline rules);
* several API keys per provider with round-robin rotation;
* retries with exponential backoff and jitter, honouring ``Retry-After``;
* a circuit breaker per provider key (closed -> open -> half-open);
* daily token/request budgets per user and globally;
* a concurrency semaphore so a burst cannot open hundreds of provider connections;
* a deterministic offline fallback that answers in Arabic and never raises.

``complete`` never raises. A caller that gets ``""`` treats it as a malformed answer, which is
already an error path in both agents.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from app.core.config import Settings
from app.services.observability import RequestTrace, current_trace
from app.services.offline_llm import GroundedTemplateLLM, OfflineToolLLM

logger = logging.getLogger(__name__)

PLACEHOLDER_KEYS = {"", "changeme", "your-nvidia-nim-api-key"}

# Reasons recorded in the trace / logs. Stable codes, no free text.
REASON_NO_PROVIDER = "no_provider_configured"
REASON_ALL_COOLING = "all_keys_cooling"
REASON_PROVIDER_ERROR = "provider_error"
REASON_BUDGET = "budget_exceeded"
REASON_BUSY = "concurrency_limit"
REASON_OFFLINE = "offline_fallback"


def estimate_tokens(text: str) -> int:
    """Cheap deterministic estimate (Arabic is close to 3 characters per token)."""
    return max(1, len(text or "") // 3)


def split_keys(*values: str) -> tuple[str, ...]:
    """Flatten comma-separated key lists, dropping placeholders and duplicates."""
    seen: list[str] = []
    for value in values:
        for raw in (value or "").split(","):
            key = raw.strip()
            if not key or key.lower() in PLACEHOLDER_KEYS or key in seen:
                continue
            seen.append(key)
    return tuple(seen)


class ChatClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


ClientFactory = Callable[["ProviderConfig", str], ChatClient]


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    base_url: str
    keys: tuple[str, ...]
    timeout_seconds: float = 30.0
    max_tokens: int = 1024


class KeyHealth:
    """Circuit breaker + cooldown for one API key. All access is guarded by the pool lock."""

    def __init__(
        self,
        key: str,
        *,
        threshold: int,
        open_seconds: float,
        auth_seconds: float,
        retry_after_default: float = 5.0,
    ):
        self.key = key
        self.threshold = max(1, threshold)
        self.open_seconds = max(0.0, open_seconds)
        self.auth_seconds = max(0.0, auth_seconds)
        self.retry_after_default = max(0.0, retry_after_default)
        self.state = "closed"
        self.failures = 0
        self.cooldown_until = 0.0
        self.open_until = 0.0
        self.successes = 0
        self.total_failures = 0
        self.last_status: int | None = None

    def is_available(self, now: float) -> bool:
        """Pure check used by status snapshots (no state transition)."""
        if now < self.cooldown_until:
            return False
        return not (self.state == "open" and now < self.open_until)

    def available(self, now: float) -> bool:
        if not self.is_available(now):
            return False
        if self.state == "open":
            self.state = "half_open"  # single probe
        return True

    def success(self) -> None:
        self.state = "closed"
        self.failures = 0
        self.cooldown_until = 0.0
        self.open_until = 0.0
        self.successes += 1

    def failure(self, *, status: int | None, retry_after: float | None, now: float) -> None:
        self.failures += 1
        self.total_failures += 1
        self.last_status = status
        if status in (401, 403):
            self.cooldown_until = now + self.auth_seconds
            self.open_until = self.cooldown_until
            self.state = "open"
            return
        delay = 0.0
        if status == 429:
            # Without a Retry-After header, assume a short quota window instead of hammering.
            delay = retry_after if retry_after is not None else self.retry_after_default
        if delay:
            self.cooldown_until = max(self.cooldown_until, now + delay)
        if self.failures >= self.threshold:
            self.state = "open"
            self.open_until = max(now + self.open_seconds, self.cooldown_until)
            self.cooldown_until = self.open_until


class KeyPool:
    """Round-robin over a provider's keys, skipping cooled-down or open keys."""

    def __init__(self, keys: tuple[str, ...], health: list[KeyHealth]):
        self._health = health
        self._lock = threading.Lock()
        self._next = 0
        self.keys = keys

    @classmethod
    def build(
        cls,
        keys: tuple[str, ...],
        *,
        threshold: int,
        open_seconds: float,
        auth_seconds: float,
        retry_after_default: float = 5.0,
    ) -> KeyPool:
        health = [
            KeyHealth(
                k,
                threshold=threshold,
                open_seconds=open_seconds,
                auth_seconds=auth_seconds,
                retry_after_default=retry_after_default,
            )
            for k in keys
        ]
        return cls(keys, health)

    def acquire(self, now: float | None = None) -> tuple[int, str] | None:
        now = time.monotonic() if now is None else now
        with self._lock:
            total = len(self._health)
            for offset in range(total):
                index = (self._next + offset) % total
                if self._health[index].available(now):
                    self._next = (index + 1) % total
                    return index, self._health[index].key
            return None

    def success(self, index: int) -> None:
        with self._lock:
            self._health[index].success()

    def failure(
        self, index: int, *, status: int | None, retry_after: float | None
    ) -> None:
        with self._lock:
            self._health[index].failure(
                status=status, retry_after=retry_after, now=time.monotonic()
            )

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            return {
                "keys_total": len(self._health),
                "keys_available": sum(1 for item in self._health if item.is_available(now)),
                "keys_open": sum(1 for item in self._health if item.state == "open"),
                "keys_half_open": sum(1 for item in self._health if item.state == "half_open"),
                "failures": sum(item.total_failures for item in self._health),
                "successes": sum(item.successes for item in self._health),
            }


class BudgetTracker:
    """Daily request/token budgets. Estimates only, reset at UTC midnight."""

    def __init__(
        self,
        *,
        global_tokens: int,
        user_tokens: int,
        global_requests: int,
        user_requests: int,
        day_provider: Callable[[], str] | None = None,
    ):
        self.global_tokens = max(0, global_tokens)
        self.user_tokens = max(0, user_tokens)
        self.global_requests = max(0, global_requests)
        self.user_requests = max(0, user_requests)
        self._day = day_provider or (lambda: datetime.now(UTC).date().isoformat())
        self._lock = threading.Lock()
        self._current_day = self._day()
        self._global = {"requests": 0, "tokens": 0}
        self._users: dict[str, dict[str, int]] = {}

    def _rollover(self) -> None:
        today = self._day()
        if today != self._current_day:
            self._current_day = today
            self._global = {"requests": 0, "tokens": 0}
            self._users.clear()

    def allows(self, user_id: str | None, tokens: int) -> bool:
        with self._lock:
            self._rollover()
            if self._global["requests"] >= self.global_requests:
                return False
            if self._global["tokens"] + tokens > self.global_tokens:
                return False
            if user_id:
                usage = self._users.get(user_id, {"requests": 0, "tokens": 0})
                if usage["requests"] >= self.user_requests:
                    return False
                if usage["tokens"] + tokens > self.user_tokens:
                    return False
            return True

    def record(self, user_id: str | None, tokens: int) -> None:
        with self._lock:
            self._rollover()
            self._global["requests"] += 1
            self._global["tokens"] += tokens
            if user_id:
                usage = self._users.setdefault(user_id, {"requests": 0, "tokens": 0})
                usage["requests"] += 1
                usage["tokens"] += tokens

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._rollover()
            return {
                "day": self._current_day,
                "global_requests": self._global["requests"],
                "global_tokens": self._global["tokens"],
                "tracked_users": len(self._users),
            }


@dataclass
class ProviderRuntime:
    config: ProviderConfig
    factory: ClientFactory
    pool: KeyPool
    _clients: dict[int, ChatClient] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def client(self, index: int) -> ChatClient:
        with self._lock:
            client = self._clients.get(index)
            if client is None:
                client = self.factory(self.config, self.pool.keys[index])
                self._clients[index] = client
            return client


class LLMGateway:
    """Provider chain with rotation, retries, circuits, budgets and an offline fallback."""

    def __init__(
        self,
        providers: list[ProviderRuntime],
        *,
        offline: ChatClient | None = None,
        budget: BudgetTracker | None = None,
        max_attempts: int = 3,
        backoff_base_seconds: float = 0.25,
        backoff_max_seconds: float = 3.0,
        max_input_tokens: int = 6000,
        max_tokens: int = 1024,
        max_concurrent_calls: int = 8,
        queue_timeout_seconds: float = 5.0,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.providers = providers
        self.offline = offline
        self.budget = budget
        self.max_attempts = max(1, max_attempts)
        self.backoff_base_seconds = max(0.0, backoff_base_seconds)
        self.backoff_max_seconds = max(0.0, backoff_max_seconds)
        self.max_input_tokens = max(256, max_input_tokens)
        self.max_tokens = max(64, max_tokens)
        self._sleep = sleeper
        self._semaphore = threading.BoundedSemaphore(max(1, max_concurrent_calls))
        self.queue_timeout_seconds = max(0.0, queue_timeout_seconds)
        self._lock = threading.Lock()
        self.calls = 0
        self.failures = 0
        self.offline_calls = 0

    # ------------------------------------------------------------- public API
    def complete(self, system: str, user: str, *, user_id: str | None = None) -> str:
        # Share the API request trace when one exists; otherwise use a throwaway trace so a
        # direct agent call never leaks state into the next call in the same context.
        trace = current_trace() or RequestTrace()
        user_id = user_id or trace.user_id
        prompt_tokens = estimate_tokens(system) + estimate_tokens(user) + self.max_tokens

        if self.budget is not None and not self.budget.allows(user_id, prompt_tokens):
            return self._degrade(system, user, trace, REASON_BUDGET, user_id)

        if not self._semaphore.acquire(timeout=self.queue_timeout_seconds):
            return self._degrade(system, user, trace, REASON_BUSY, user_id)
        try:
            trimmed = self._trim(system, user, trace)
            result = self._call_chain(trimmed[0], trimmed[1], trace, user_id)
            if result is not None:
                return result
            reason = trace.fallback_reason or REASON_PROVIDER_ERROR
            return self._offline(system, user, trace, reason, user_id)
        finally:
            self._semaphore.release()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            calls, failures, offline = self.calls, self.failures, self.offline_calls
        return {
            "calls": calls,
            "failures": failures,
            "offline_calls": offline,
            "providers": [
                {"name": provider.config.name, "model": provider.config.model,
                 **provider.pool.snapshot()}
                for provider in self.providers
            ],
            "budget": self.budget.snapshot() if self.budget else None,
            "offline_available": self.offline is not None,
        }

    # ------------------------------------------------------------- internals
    def _call_chain(
        self, system: str, user: str, trace: RequestTrace, user_id: str | None
    ) -> str | None:
        if not self.providers:
            trace.degrade(REASON_NO_PROVIDER)
            return None

        attempted = False
        saw_error = False
        for attempt in range(1, self.max_attempts + 1):
            wait_hint = 0.0
            for provider in self.providers:
                # Try each key at most once per round, so a dead key rotates instead of
                # absorbing every attempt.
                used: set[int] = set()
                for _ in range(len(provider.pool.keys)):
                    picked = provider.pool.acquire()
                    if picked is None:
                        break
                    index, _key = picked
                    if index in used:
                        break
                    used.add(index)
                    attempted = True
                    trace.note_provider(provider.config.name)
                    try:
                        text = provider.client(index).complete(system, user)
                    except Exception as exc:  # noqa: BLE001 - provider errors never escape
                        saw_error = True
                        status = getattr(exc, "status_code", None)
                        retry_after = getattr(exc, "retry_after_seconds", None)
                        if isinstance(retry_after, int | float):
                            wait_hint = max(wait_hint, float(retry_after))
                        provider.pool.failure(index, status=status, retry_after=retry_after)
                        logger.warning(
                            "llm provider error provider=%s status=%s type=%s",
                            provider.config.name,
                            status,
                            type(exc).__name__,
                        )
                        continue
                    provider.pool.success(index)
                    if not isinstance(text, str):
                        continue
                    self._record_call(trace, user_id, system, user, text, degraded=False)
                    return text

            if attempt < self.max_attempts:
                trace.note_retry()
                # Honour Retry-After when the provider sent one, otherwise back off.
                self._sleep(max(self._backoff(attempt), wait_hint))

        with self._lock:
            self.failures += 1
        if not attempted:
            trace.degrade(REASON_ALL_COOLING)
        elif saw_error:
            trace.degrade(REASON_PROVIDER_ERROR)
        return None

    def _degrade(
        self,
        system: str,
        user: str,
        trace: RequestTrace,
        reason: str,
        user_id: str | None,
    ) -> str:
        trace.degrade(reason)
        return self._offline(system, user, trace, reason, user_id)

    def _offline(
        self,
        system: str,
        user: str,
        trace: RequestTrace,
        reason: str,
        user_id: str | None,
    ) -> str:
        trace.degrade(reason)
        if self.offline is None:
            return ""
        with self._lock:
            self.offline_calls += 1
        try:
            text = self.offline.complete(system, user)
        except Exception:  # noqa: BLE001 - offline mode is the last line of defence
            logger.warning("offline fallback failed type=%s", "OfflineError")
            return ""
        self._record_call(trace, user_id, system, user, text, degraded=True)
        return text

    def _record_call(
        self,
        trace: RequestTrace,
        user_id: str | None,
        system: str,
        user: str,
        answer: str,
        *,
        degraded: bool,
    ) -> None:
        tokens = (
            estimate_tokens(system)
            + estimate_tokens(user)
            + estimate_tokens(answer)
        )
        if not degraded:
            if self.budget is not None:
                self.budget.record(user_id, tokens)
            with self._lock:
                self.calls += 1
        trace.note_tokens(tokens)
        if degraded:
            trace.degrade(trace.fallback_reason or REASON_OFFLINE)

    def _trim(self, system: str, user: str, trace: RequestTrace) -> tuple[str, str]:
        budget = self.max_input_tokens - estimate_tokens(system)
        if budget <= 0:
            return system[: self.max_input_tokens * 3], ""
        if estimate_tokens(user) <= budget:
            return system, user
        keep = max(1, budget) * 3
        head = user[: int(keep * 0.7)]
        tail = user[-int(keep * 0.3) :] if keep > 4 else ""
        logger.warning("llm prompt trimmed tokens_estimate=%s", estimate_tokens(user))
        trace.note_tokens(estimate_tokens(user) - estimate_tokens(head + tail))
        return system, f"{head}\n...\n{tail}"

    def _backoff(self, attempt: int) -> float:
        raw = self.backoff_base_seconds * (2 ** (attempt - 1))
        jitter = random.uniform(0, self.backoff_base_seconds)
        return min(self.backoff_max_seconds, raw + jitter)


# --------------------------------------------------------------------------- builders
def _nim_factory(config: ProviderConfig, key: str) -> ChatClient:
    from app.agents.complaint_agent.nim_client import NvidiaNimClient

    return NvidiaNimClient(
        api_key=key,
        model=config.model,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
        max_tokens=config.max_tokens,
    )


def build_gateway(settings: Settings) -> LLMGateway:
    """Build the gateway from settings. Any OpenAI-compatible endpoint works."""
    primary_keys = split_keys(settings.llm_api_keys, settings.llm_api_key)
    secondary_keys = split_keys(settings.llm_secondary_api_keys)
    max_call = min(float(settings.llm_timeout_seconds), float(settings.llm_max_call_seconds))

    providers: list[ProviderRuntime] = []
    if primary_keys:
        config = ProviderConfig(
            name=settings.llm_provider or "nvidia_nim",
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            keys=primary_keys,
            timeout_seconds=max(1.0, max_call),
            max_tokens=settings.llm_max_tokens,
        )
        providers.append(
            ProviderRuntime(
                config=config,
                factory=_nim_factory,
                pool=KeyPool.build(
                    primary_keys,
                    threshold=settings.llm_circuit_failure_threshold,
                    open_seconds=settings.llm_circuit_open_seconds,
                    auth_seconds=settings.llm_auth_cooldown_seconds,
                    retry_after_default=settings.llm_retry_after_default_seconds,
                ),
            )
        )

    if secondary_keys and settings.llm_secondary_model and settings.llm_secondary_base_url:
        config = ProviderConfig(
            name=settings.llm_secondary_name or "secondary",
            model=settings.llm_secondary_model,
            base_url=settings.llm_secondary_base_url,
            keys=secondary_keys,
            timeout_seconds=max(1.0, float(settings.llm_secondary_timeout_seconds)),
            max_tokens=settings.llm_max_tokens,
        )
        providers.append(
            ProviderRuntime(
                config=config,
                factory=_nim_factory,
                pool=KeyPool.build(
                    secondary_keys,
                    threshold=settings.llm_circuit_failure_threshold,
                    open_seconds=settings.llm_circuit_open_seconds,
                    auth_seconds=settings.llm_auth_cooldown_seconds,
                    retry_after_default=settings.llm_retry_after_default_seconds,
                ),
            )
        )

    offline = None
    if settings.llm_offline_fallback:
        offline = OfflineToolLLM(GroundedTemplateLLM())

    budget = BudgetTracker(
        global_tokens=settings.llm_global_daily_token_budget,
        user_tokens=settings.llm_user_daily_token_budget,
        global_requests=settings.llm_global_daily_request_budget,
        user_requests=settings.llm_user_daily_request_budget,
    )

    return LLMGateway(
        providers,
        offline=offline,
        budget=budget,
        max_attempts=settings.llm_max_attempts,
        backoff_base_seconds=settings.llm_backoff_base_seconds,
        backoff_max_seconds=settings.llm_backoff_max_seconds,
        max_input_tokens=settings.llm_max_input_tokens,
        max_tokens=settings.llm_max_tokens,
        max_concurrent_calls=settings.llm_max_concurrent_calls,
        queue_timeout_seconds=settings.llm_queue_timeout_seconds,
    )

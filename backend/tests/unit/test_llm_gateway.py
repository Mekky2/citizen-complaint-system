"""Resilience tests for the shared LLM gateway (all offline, no network)."""

from __future__ import annotations

import logging
import time

import pytest

from app.agents.complaint_agent.nim_client import LLMProviderError
from app.services.llm_gateway import (
    BudgetTracker,
    KeyPool,
    LLMGateway,
    ProviderConfig,
    ProviderRuntime,
    build_gateway,
)
from app.services.observability import reset_trace, start_trace


class ScriptedClient:
    """Returns scripted outcomes: strings are answers, exceptions are raised."""

    def __init__(self, script: list[object], calls: list[str] | None = None):
        self.script = list(script)
        self.calls = calls if calls is not None else []

    def complete(self, system: str, user: str) -> str:
        self.calls.append(user)
        if not self.script:
            return "ok"
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return str(item)


class OfflineStub:
    def __init__(self, answer: str = "إجابة احتياطية عربية"):
        self.answer = answer
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return self.answer


def _provider(
    name: str, clients: dict[str, ScriptedClient], keys: tuple[str, ...], **kw
) -> ProviderRuntime:
    config = ProviderConfig(name=name, model="test-model", base_url="http://test", keys=keys)
    return ProviderRuntime(
        config=config,
        factory=lambda _config, key: clients[key],
        pool=KeyPool.build(
            keys,
            threshold=kw.get("threshold", 3),
            open_seconds=kw.get("open_seconds", 30.0),
            auth_seconds=kw.get("auth_seconds", 300.0),
        ),
    )


def _gateway(providers, offline=None, **kw) -> LLMGateway:
    return LLMGateway(
        providers,
        offline=offline or OfflineStub(),
        max_attempts=kw.pop("max_attempts", 2),
        backoff_base_seconds=kw.pop("backoff_base_seconds", 0.0),
        backoff_max_seconds=kw.pop("backoff_max_seconds", 0.0),
        **kw,
    )


@pytest.fixture(autouse=True)
def _fresh_trace():
    reset_trace()
    yield
    reset_trace()


def test_retries_after_429_and_honours_retry_after():
    waits: list[float] = []

    def sleeper(seconds: float) -> None:
        waits.append(seconds)
        time.sleep(seconds)

    client = ScriptedClient(
        [
            LLMProviderError("rate", transient=True, status_code=429, retry_after_seconds=0.01),
            "نجاح",
        ]
    )
    gateway = _gateway(
        [_provider("primary", {"k1": client}, ("k1",))],
        max_attempts=2,
        sleeper=sleeper,
    )
    trace = start_trace()

    assert gateway.complete("sys", "user") == "نجاح"
    assert trace.retries == 1
    assert waits and waits[0] >= 0.01
    assert trace.degraded is False


def test_exhausted_key_rotates_to_the_next_key():
    dead = ScriptedClient([LLMProviderError("denied", transient=False, status_code=401)])
    alive = ScriptedClient(["من المفتاح الثاني"])
    gateway = _gateway(
        [_provider("primary", {"a": dead, "b": alive}, ("a", "b"))],
        max_attempts=1,
    )

    assert gateway.complete("sys", "user") == "من المفتاح الثاني"
    snapshot = gateway.snapshot()["providers"][0]
    assert snapshot["failures"] == 1
    assert snapshot["successes"] == 1


def test_primary_down_falls_through_to_secondary_provider():
    primary = ScriptedClient([LLMProviderError("denied", transient=False, status_code=403)])
    secondary = ScriptedClient(["من المزوّد الثاني"])
    gateway = _gateway(
        [
            _provider("mistral", {"a": primary}, ("a",)),
            _provider("secondary", {"b": secondary}, ("b",)),
        ],
        max_attempts=1,
    )

    assert gateway.complete("sys", "user") == "من المزوّد الثاني"


def test_all_providers_down_answers_offline_and_marks_degraded():
    offline = OfflineStub()
    broken = ScriptedClient([LLMProviderError("boom", transient=True, status_code=500)])
    gateway = _gateway(
        [_provider("primary", {"k": broken}, ("k",))], offline=offline, max_attempts=1
    )
    trace = start_trace()

    assert gateway.complete("sys", "user") == offline.answer
    assert offline.calls == 1
    assert trace.degraded is True
    assert trace.fallback_reason == "provider_error"


def test_timeout_is_retried_then_succeeds():
    client = ScriptedClient([LLMProviderError("timeout", transient=True), "بعد الإعادة"])
    gateway = _gateway([_provider("primary", {"k": client}, ("k",))], max_attempts=2)
    trace = start_trace()

    assert gateway.complete("sys", "user") == "بعد الإعادة"
    assert trace.retries == 1


def test_circuit_breaker_opens_skips_then_half_opens():
    client = ScriptedClient(
        [
            LLMProviderError("boom", transient=True, status_code=500),
            LLMProviderError("boom", transient=True, status_code=500),
            "نجاح بعد نصف الفتح",
        ]
    )
    gateway = _gateway(
        [_provider("primary", {"k": client}, ("k",), threshold=2, open_seconds=0.05)],
        max_attempts=1,
    )

    assert gateway.complete("sys", "user") == "إجابة احتياطية عربية"
    assert gateway.complete("sys", "user") == "إجابة احتياطية عربية"
    assert gateway.snapshot()["providers"][0]["keys_open"] == 1

    start_after_open = start_trace()
    assert gateway.complete("sys", "user") == "إجابة احتياطية عربية"
    assert start_after_open.fallback_reason == "all_keys_cooling"

    time.sleep(0.06)  # let the circuit move to half-open
    assert gateway.complete("sys", "user") == "نجاح بعد نصف الفتح"
    # half-open probe succeeded -> the circuit closes again
    assert gateway.snapshot()["providers"][0]["keys_open"] == 0


def test_budget_exhausted_degrades_without_calling_a_provider():
    client = ScriptedClient(["لن تُستدعى"])
    budget = BudgetTracker(global_tokens=5, user_tokens=5, global_requests=10, user_requests=10)
    gateway = _gateway(
        [_provider("primary", {"k": client}, ("k",))],
        budget=budget,
    )
    trace = start_trace()

    assert gateway.complete("sys", "user with a phone 01123456789", user_id="u1") == (
        "إجابة احتياطية عربية"
    )
    assert client.calls == []
    assert trace.fallback_reason == "budget_exceeded"


def test_no_pii_or_prompt_text_in_logs(caplog):
    broken = ScriptedClient([LLMProviderError("boom", transient=True, status_code=500)])
    gateway = _gateway([_provider("primary", {"k": broken}, ("k",))], max_attempts=1)
    secret_phone = "01123456789"

    with caplog.at_level(logging.WARNING):
        gateway.complete("system prompt", f"شكوى رقم {secret_phone}")

    assert secret_phone not in caplog.text
    assert "شكوى رقم" not in caplog.text


def test_build_gateway_without_keys_is_offline_only():
    from app.core.config import Settings

    gateway = build_gateway(Settings(llm_api_key="", llm_api_keys=""))
    assert gateway.providers == []
    assert gateway.offline is not None
    trace = start_trace()
    answer = gateway.complete("sys", "user")
    assert answer
    assert trace.degraded is True
    assert trace.fallback_reason == "no_provider_configured"


def test_pools_are_isolated_and_round_robin():
    pool = KeyPool.build(("a", "b"), threshold=1, open_seconds=10, auth_seconds=10)
    assert pool.acquire()[1] == "a"
    assert pool.acquire()[1] == "b"
    assert pool.acquire()[1] == "a"


def test_429_without_retry_after_uses_the_default_cooldown():
    pool = KeyPool.build(
        ("k",), threshold=1, open_seconds=10, auth_seconds=10, retry_after_default=60
    )
    pool.failure(0, status=429, retry_after=None)

    assert pool.acquire() is None  # cooling down instead of retrying immediately
    assert pool.snapshot()["keys_available"] == 0

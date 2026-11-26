"""API-level resilience: degradation, overload, rate limits and concurrent sessions."""

from __future__ import annotations

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.agents.complaint_agent.nim_client import LLMProviderError
from app.main import create_app
from app.services.llm_gateway import (
    KeyPool,
    LLMGateway,
    ProviderConfig,
    ProviderRuntime,
)
from app.services.observability import reset_trace
from app.services.offline_llm import GroundedTemplateLLM, OfflineToolLLM
from app.services.rate_limit import ConcurrencyGate, SlidingWindowLimiter
from app.services.runtime import get_runtime, reset_runtime
from app.services.session_store import InMemorySessionStore
from app.services.ticket_store import InMemoryTicketStore

OFFLINE = OfflineToolLLM(GroundedTemplateLLM())


class FlakyClient:
    """Valid offline answers, but randomly fails like a real provider under load."""

    def __init__(self, *, fail_rate: float = 0.2, delay: float = 0.0):
        self.fail_rate = fail_rate
        self.delay = delay
        self.calls = 0
        self._lock = threading.Lock()

    def complete(self, system: str, user: str) -> str:
        with self._lock:
            self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if random.random() < self.fail_rate:
            status = random.choice([429, 500, 503])
            raise LLMProviderError("flaky", transient=True, status_code=status)
        return OFFLINE.complete(system, user)


class DeadClient:
    def __init__(self, status: int = 403):
        self.status = status

    def complete(self, system: str, user: str) -> str:
        raise LLMProviderError("denied", transient=False, status_code=self.status)


def _gateway(client, *, keys: tuple[str, ...] = ("k1", "k2", "k3"), attempts: int = 2):
    config = ProviderConfig(name="fake", model="test", base_url="http://x", keys=keys)
    provider = ProviderRuntime(
        config=config,
        factory=lambda _config, _key: client,
        pool=KeyPool.build(keys, threshold=5, open_seconds=5, auth_seconds=5),
    )
    return LLMGateway(
        [provider],
        offline=OFFLINE,
        max_attempts=attempts,
        backoff_base_seconds=0.001,
        backoff_max_seconds=0.005,
    )


def _install(rt, gateway) -> None:
    rt.gateway = gateway
    rt.llm = gateway
    rt.rag_llm = gateway


@pytest.fixture()
def client():
    reset_runtime()
    reset_trace()
    rt = get_runtime()
    rt.sessions = InMemorySessionStore(max_entries=10_000, max_history_messages=20)
    rt.ticket_store = InMemoryTicketStore()
    rt.answer_cache.clear()
    rt.rate_limiter = SlidingWindowLimiter(per_minute=10_000, burst=10_000)
    rt.request_gate = ConcurrencyGate(max_concurrent=32)
    with TestClient(create_app()) as test_client:
        yield test_client
    reset_runtime()
    reset_trace()


def _post(client, message: str, session_id: str):
    # No user_id: the limiter falls back to the client IP, which is one value in tests.
    return client.post("/api/v1/chat", json={"message": message, "session_id": session_id})


def test_degraded_mode_still_answers_arabic_and_creates_tickets(client):
    rt = get_runtime()
    _install(rt, _gateway(DeadClient(403)))

    rag = _post(client, "كيف أقدم شكوى؟", "deg-rag")
    assert rag.status_code == 200, rag.text
    body = rag.json()
    assert body["degraded"] is True
    assert body["found_in_kb"] is True
    assert body["sources"], "offline mode must still cite the knowledge base"
    assert any("\u0600" <= char <= "\u06ff" for char in body["reply_ar"])

    first = _post(client, "تسريب مياه في ماسورة بشارع النيل", "deg-complaint")
    assert first.status_code == 200
    assert first.json()["type"] == "complaint"
    assert first.json()["degraded"] is True

    confirmed = _post(client, "نعم أكد الإرسال", "deg-complaint")
    assert confirmed.status_code == 200
    ticket = confirmed.json()["ticket"]
    assert ticket and ticket["status"] == "Pending"


def test_health_ready_and_admin_status_hide_keys(client):
    rt = get_runtime()
    _install(rt, _gateway(FlakyClient(fail_rate=0.0), keys=("sk-super-secret-key",)))

    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["knowledge"]["documents"] == 15

    status = client.get("/api/v1/admin/status")
    assert status.status_code == 200
    assert "sk-super-secret-key" not in status.text
    assert status.json()["llm"]["providers"][0]["keys_total"] == 1


def test_rate_limit_returns_429_with_retry_after(client):
    rt = get_runtime()
    _install(rt, _gateway(FlakyClient(fail_rate=0.0)))
    rt.rate_limiter = SlidingWindowLimiter(per_minute=1, burst=1)

    assert _post(client, "كيف أقدم شكوى؟", "rl1").status_code == 200
    limited = _post(client, "كيف أقدم شكوى؟", "rl2")

    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    assert "المحاولة" in limited.json()["detail"]


def test_overload_returns_503_with_retry_after(client):
    rt = get_runtime()
    slow = FlakyClient(fail_rate=0.0, delay=0.4)
    _install(rt, _gateway(slow))
    rt.request_gate = ConcurrencyGate(max_concurrent=1)
    rt.settings.api_queue_timeout_seconds = 0.02

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda i: _post(client, "كيف أقدم شكوى؟", f"busy-{i}"),
                range(4),
            )
        )

    codes = [response.status_code for response in results]
    assert 503 in codes
    for response in results:
        if response.status_code == 503:
            assert "Retry-After" in response.headers
            assert "مشغولة" in response.json()["detail"]


def test_double_confirmation_creates_one_ticket(client):
    rt = get_runtime()
    _install(rt, _gateway(FlakyClient(fail_rate=0.0)))

    assert _post(client, "حفرة في شارع النيل", "double").status_code == 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: _post(client, "نعم أكد الإرسال", "double"),
                range(2),
            )
        )

    assert [response.status_code for response in responses] == [200, 200]
    assert len(client.get("/api/v1/tickets").json()) == 1


def test_hundred_concurrent_sessions_are_isolated_and_never_500(client):
    rt = get_runtime()
    flaky = FlakyClient(fail_rate=0.25, delay=0.002)
    _install(rt, _gateway(flaky))
    rt.answer_cache.clear()

    sessions = 120

    def run(index: int) -> tuple[int, int, dict, dict]:
        marker = f"Z{index}Q"
        first = _post(
            client,
            f"تسريب مياه في ماسورة بشارع النيل في الجيزة رقم {marker}",
            f"load-{index}",
        )
        confirmed = _post(client, "نعم أكد الإرسال", f"load-{index}")
        return index, first.status_code, first.json(), confirmed.json()

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=40) as pool:
        results = list(pool.map(run, range(sessions)))
    elapsed = time.perf_counter() - started

    assert all(code == 200 for _index, code, _first, _confirmed in results)
    for index, _code, first, confirmed in results:
        assert first["type"] == "complaint"
        assert f"Z{index}Q" in first["reply_ar"], "a reply must belong to its own session"
        assert confirmed["ticket"]["status"] == "Pending"
        assert confirmed["ticket"]["description"].find(f"Z{index}Q") >= 0

    tickets = client.get("/api/v1/tickets").json()
    assert len(tickets) == sessions
    assert len({ticket["ticket_id"] for ticket in tickets}) == sessions
    assert elapsed < 60, f"unbounded latency: {elapsed:.1f}s"
    # The breaker deliberately sheds load after repeated failures, so most turns may be
    # answered offline; what matters is that the paid path was exercised.
    assert flaky.calls >= 1

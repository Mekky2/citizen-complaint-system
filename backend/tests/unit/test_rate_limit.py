"""Per-client rate limiting and the bounded in-flight gate."""

from __future__ import annotations

from app.services.rate_limit import ConcurrencyGate, SlidingWindowLimiter


def test_burst_then_reject_with_retry_after():
    now = [0.0]
    limiter = SlidingWindowLimiter(per_minute=3, burst=2, clock=lambda: now[0])

    assert limiter.allow("ip1") == (True, 0.0)
    assert limiter.allow("ip1") == (True, 0.0)
    allowed, retry_after = limiter.allow("ip1")
    assert allowed is False
    assert retry_after >= 1.0

    # A different client is unaffected.
    assert limiter.allow("ip2")[0] is True


def test_window_slides_and_frees_slots():
    now = [0.0]
    limiter = SlidingWindowLimiter(per_minute=1, burst=1, clock=lambda: now[0])
    assert limiter.allow("ip")[0] is True
    assert limiter.allow("ip")[0] is False

    now[0] = 61.0
    assert limiter.allow("ip")[0] is True


def test_concurrency_gate_waits_then_rejects():
    gate = ConcurrencyGate(max_concurrent=1)

    assert gate.acquire(timeout=0.01) is True
    assert gate.acquire(timeout=0.01) is False
    assert gate.snapshot()["rejected"] == 1

    gate.release()
    assert gate.acquire(timeout=0.01) is True
    gate.release()


def test_extra_release_never_raises():
    gate = ConcurrencyGate(max_concurrent=1)
    gate.release()  # spurious release must not crash a request
    assert gate.acquire(timeout=0.01) is True
    gate.release()

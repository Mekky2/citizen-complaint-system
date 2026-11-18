"""Session isolation, TTL, size cap and history trimming."""

from __future__ import annotations

import threading

from app.services.session_store import InMemorySessionStore


def test_sessions_are_isolated():
    store = InMemorySessionStore()
    first = store.get("u1")
    second = store.get("u2")

    first.draft.description = "تسريب مياه"
    first.stage = "awaiting_confirmation"

    assert second.draft.description == ""
    assert second.stage == "collecting"
    assert first is store.get("u1")


def test_ttl_expires_idle_sessions():
    now = [1000.0]
    store = InMemorySessionStore(ttl_seconds=10, clock=lambda: now[0])
    store.get("old").turn_count = 5

    now[0] += 11
    store.get("new")

    assert store.snapshot()["sessions"] == 1
    assert store.get("old").turn_count == 0  # fresh session, nothing leaked


def test_size_cap_evicts_the_oldest_session():
    store = InMemorySessionStore(max_entries=2)
    store.get("a")
    store.get("b")
    store.get("c")

    assert store.snapshot()["evictions"] == 1


def test_history_is_trimmed():
    store = InMemorySessionStore(max_history_messages=4)
    session = store.get("trim")
    session.history = [{"role": "user", "content": str(i)} for i in range(10)]

    store.get("trim")
    assert len(session.history) == 4
    assert session.history[-1]["content"] == "9"


def test_per_session_lock_serialises_writes():
    store = InMemorySessionStore()
    session = store.get("lock")

    def turn():
        with store.lock("lock") as locked:
            current = locked.turn_count
            locked.turn_count = current + 1

    threads = [threading.Thread(target=turn) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert session.turn_count == 20


def test_turns_in_different_sessions_do_not_block_each_other():
    store = InMemorySessionStore()
    barrier = threading.Barrier(2)
    errors: list[str] = []

    def worker(session_id: str):
        try:
            with store.lock(session_id):
                barrier.wait(timeout=2)
        except threading.BrokenBarrierError:
            errors.append(session_id)

    threads = [threading.Thread(target=worker, args=(sid,)) for sid in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []

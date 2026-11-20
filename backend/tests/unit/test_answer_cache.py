"""Answer cache: TTL, size, re-ingest invalidation and no plaintext questions."""

from __future__ import annotations

from app.services.answer_cache import AnswerCache, cache_key


def test_cache_hit_and_miss():
    cache = AnswerCache()
    assert cache.get("كيف أقدم شكوى؟") is None

    cache.set("كيف أقدم شكوى؟", {"reply_ar": "answer"})
    assert cache.get("كيف أقدم شكوى؟") == {"reply_ar": "answer"}
    assert cache.snapshot()["hits"] == 1


def test_ttl_expires_entries():
    now = [0.0]
    cache = AnswerCache(ttl_seconds=5, clock=lambda: now[0])
    cache.set("q", {"reply_ar": "a"})

    now[0] = 6
    assert cache.get("q") is None


def test_reingestion_invalidates_the_cache():
    version = [1]
    cache = AnswerCache(version_provider=lambda: version[0])
    cache.set("q", {"reply_ar": "a"})
    assert cache.get("q") is not None

    version[0] = 2  # knowledge base re-ingested
    assert cache.get("q") is None


def test_size_limit_evicts_oldest():
    cache = AnswerCache(max_entries=2)
    cache.set("a", {"reply_ar": "a"})
    cache.set("b", {"reply_ar": "b"})
    cache.set("c", {"reply_ar": "c"})

    assert cache.get("a") is None
    assert cache.get("c") is not None


def test_key_is_hashed_and_normalisation_is_stable():
    key = cache_key("كَيْفَ أقدّم شكوى؟")
    assert key == cache_key("كيف اقدم شكوى؟")
    assert "شكوى" not in key
    assert len(key) == 64  # sha256 hex


def test_answer_payload_is_copied_not_shared():
    cache = AnswerCache()
    answer = {"reply_ar": "a", "sources": []}
    cache.set("q", answer)
    fetched = cache.get("q")
    fetched["reply_ar"] = "mutated"

    assert cache.get("q")["reply_ar"] == "a"

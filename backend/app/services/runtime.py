"""Application runtime wiring.

One object per process builds the knowledge base, the LLM gateway, the stores and the two
agents. Everything is offline-capable: without keys the gateway runs in rule/template mode, so
``/api/v1/chat`` keeps answering in Arabic instead of failing.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agents.complaint_agent.conversation import (
    ComplaintSession,
    handle_message,
    looks_like_complaint,
    new_session,
)
from app.agents.orchestrator.rag_adapter import KnowledgeBaseRetriever
from app.agents.rag_agent.agent import RAGAgent
from app.core.config import Settings, get_settings
from app.knowledge_base.embeddings import HashingEmbeddingProvider, build_embedding_provider
from app.knowledge_base.store import InMemoryKnowledgeBase
from app.services.answer_cache import AnswerCache
from app.services.emergency_numbers import FileEmergencyNumbers, emergency_numbers_singleton
from app.services.llm_gateway import LLMGateway, build_gateway
from app.services.observability import RequestTrace, current_trace, reset_trace, set_trace
from app.services.rate_limit import ConcurrencyGate, SlidingWindowLimiter
from app.services.session_store import InMemorySessionStore
from app.services.ticket_store import InMemoryTicketStore, ticket_store_singleton

logger = logging.getLogger(__name__)

ACTIVE_COMPLAINT_STAGES = {"collecting", "awaiting_confirmation"}


class _SimpleHistory:
    """Minimal conversation history for a single request."""

    def __init__(self) -> None:
        self.turns: list[dict[str, str]] = []

    def add_turn(self, role: str, content: str, metadata: dict | None = None) -> None:
        self.turns.append({"role": role, "content": content})

    def get_recent_turns(self, n: int = 5) -> list[dict[str, str]]:
        return self.turns[-n:]

    def clear(self) -> None:
        self.turns.clear()


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.embedding_provider = _embedding_provider(settings)
        self.knowledge_base = InMemoryKnowledgeBase(self.embedding_provider)
        self.knowledge_stats = self._load_knowledge(settings.knowledge_dir)

        # The gateway is the only LLM entry point. ``llm``/``rag_llm`` are kept as aliases so
        # existing agent wiring and tests continue to work unchanged.
        self.gateway: LLMGateway = build_gateway(settings)
        self.llm: Any = self.gateway
        self.rag_llm: Any = self.gateway

        self.emergency_numbers: FileEmergencyNumbers = emergency_numbers_singleton()
        self.ticket_store: InMemoryTicketStore = ticket_store_singleton()
        self.sessions = InMemorySessionStore(
            ttl_seconds=settings.session_ttl_seconds,
            max_entries=settings.session_max_entries,
            max_history_messages=settings.session_max_history_messages,
            max_turns=settings.complaint_max_turns,
        )
        self.answer_cache = AnswerCache(
            ttl_seconds=settings.rag_cache_ttl_seconds,
            max_entries=settings.rag_cache_max_entries,
            version_provider=lambda: self.knowledge_base.version,
        )
        self.rate_limiter = SlidingWindowLimiter(
            per_minute=settings.rate_limit_per_minute,
            burst=settings.rate_limit_burst,
        )
        self.request_gate = ConcurrencyGate(max_concurrent=settings.api_max_concurrent_requests)
        self._retriever: KnowledgeBaseRetriever | None = None

    def _load_knowledge(self, directory: str) -> dict[str, int]:
        path = Path(directory)
        if not path.is_absolute():
            # backend/data/knowledge regardless of the current working directory
            path = Path(__file__).resolve().parents[2] / directory
        if not path.exists():
            logger.warning("knowledge directory not found: %s", path)
            return {"inserted": 0, "updated": 0, "skipped": 0, "documents": 0}
        return self.knowledge_base.ingest_directory(str(path))

    # ------------------------------------------------------------- accessors
    def session(self, session_id: str) -> ComplaintSession:
        return self.sessions.get(session_id)

    def rag_agent(self) -> RAGAgent:
        return RAGAgent(
            llm=self.rag_llm,
            knowledge_base=self.knowledge_base,
            embedding_provider=self.embedding_provider,
            conversation=_SimpleHistory(),
            emergency_numbers=self.emergency_numbers,
            top_k=self.settings.rag_top_k,
        )

    def rag_retriever(self) -> KnowledgeBaseRetriever:
        if self._retriever is None:
            self._retriever = KnowledgeBaseRetriever(self.knowledge_base)
        return self._retriever

    # ------------------------------------------------------------- chat flow
    def chat(self, message: str, session_id: str, user_id: str | None = None) -> dict[str, Any]:
        """Run one turn. Synchronous: the API calls it through ``asyncio.to_thread``."""
        existing = current_trace()
        if existing is not None:
            if user_id:
                existing.user_id = user_id
            return self._chat(message, session_id, trace=existing)
        # Direct callers (tests, scripts) still get accurate degraded flags without leaking a
        # trace into the next call in the same context.
        trace = RequestTrace(user_id=user_id)
        set_trace(trace)
        try:
            return self._chat(message, session_id, trace=trace)
        finally:
            reset_trace()

    def _chat(self, message: str, session_id: str, *, trace: RequestTrace) -> dict[str, Any]:
        rag = self.rag_agent()
        with self.sessions.lock(session_id) as session:
            if session.stage in ACTIVE_COMPLAINT_STAGES:
                return self._complaint_turn(message, session, rag, trace)
            intent = rag.detect_intent(message)
            if intent == "complaint" or looks_like_complaint(message):
                return self._complaint_turn(message, session, rag, trace)
            return self._rag_turn(message, session_id, rag, trace)

    def _complaint_turn(self, message, session, rag, trace) -> dict[str, Any]:
        result = handle_message(
            session,
            message,
            llm=self.gateway,
            store=self.ticket_store,
            emergency_numbers=self.emergency_numbers,
        )
        if result.get("handoff_to") == "rag":
            rag_result = rag.run(
                {
                    "query": message,
                    "ticket_id": f"SESSION-{session.session_id}",
                    "session_id": session.session_id,
                    "conversation_history": [],
                    "tool_calls": 0,
                }
            )
            return {
                "type": "rag",
                "session_id": session.session_id,
                "reply_ar": rag_result["answer"],
                "stage": session.stage,
                "ticket": None,
                "missing_fields": [],
                "requires_confirmation": False,
                "handoff_to": "rag",
                "sources": _sources(rag_result),
                "confidence": rag_result["confidence"],
                "found_in_kb": rag_result["found_in_kb"],
                "review_notes": rag_result["review_notes"],
                "degraded": trace.degraded,
                "request_id": trace.request_id,
            }
        return {
            "type": "complaint",
            "session_id": session.session_id,
            "reply_ar": result["reply_ar"],
            "stage": result["stage"],
            "ticket": result.get("ticket"),
            "missing_fields": result.get("missing_fields", []),
            "requires_confirmation": result.get("requires_confirmation", False),
            "handoff_to": result.get("handoff_to"),
            "sources": [],
            "confidence": None,
            "found_in_kb": None,
            "review_notes": result.get("review_notes", []),
            "degraded": trace.degraded,
            "request_id": trace.request_id,
        }

    def _rag_turn(self, message, session_id, rag, trace) -> dict[str, Any]:
        cached = self.answer_cache.get(message)
        if cached is not None:
            trace.cache_hit = True
            return {**cached, "session_id": session_id, "degraded": trace.degraded,
                    "request_id": trace.request_id}

        rag_result = rag.run(
            {
                "query": message,
                "ticket_id": f"SESSION-{session_id}",
                "session_id": session_id,
                "conversation_history": [],
                "tool_calls": 0,
            }
        )
        payload = {
            "type": "rag",
            "session_id": session_id,
            "reply_ar": rag_result["answer"],
            "stage": None,
            "ticket": None,
            "missing_fields": [],
            "requires_confirmation": False,
            "handoff_to": None,
            "sources": _sources(rag_result),
            "confidence": rag_result["confidence"],
            "found_in_kb": rag_result["found_in_kb"],
            "review_notes": rag_result["review_notes"],
        }
        # Never cache a degraded answer: once the provider recovers we want a fresh one.
        if rag_result.get("found_in_kb") and not trace.degraded:
            self.answer_cache.set(message, payload)
        return {**payload, "degraded": trace.degraded, "request_id": trace.request_id}

    # ------------------------------------------------------------- readiness
    def readiness(self) -> dict[str, Any]:
        documents = len(self.knowledge_base.documents)
        chunks = self.knowledge_base.chunk_count
        providers = self.gateway.snapshot()["providers"] if self.gateway else []
        paid_available = any(provider["keys_available"] for provider in providers)
        return {
            "status": "ready" if documents and chunks else "degraded",
            "knowledge": {"documents": documents, "chunks": chunks},
            "llm": {
                "providers": providers,
                "paid_provider_available": paid_available,
                "offline_fallback": self.settings.llm_offline_fallback,
            },
            "sessions": self.sessions.snapshot(),
            "cache": self.answer_cache.snapshot(),
        }

    def admin_status(self) -> dict[str, Any]:
        """Operational snapshot without keys, prompts or complaint text."""
        return {
            "env": self.settings.app_env,
            "degraded": (current_trace().degraded if current_trace() else False),
            "llm": self.gateway.snapshot(),
            "sessions": self.sessions.snapshot(),
            "cache": self.answer_cache.snapshot(),
            "rate_limit": self.rate_limiter.snapshot(),
            "request_gate": self.request_gate.snapshot(),
            "tickets": len(self.ticket_store.list()),
            "knowledge": {
                "documents": len(self.knowledge_base.documents),
                "chunks": self.knowledge_base.chunk_count,
                "version": self.knowledge_base.version,
            },
        }


def _sources(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        source.model_dump() if hasattr(source, "model_dump") else dict(source)
        for source in result.get("sources", [])
    ]


def _embedding_provider(settings: Settings):
    try:
        return build_embedding_provider(settings)
    except (ValueError, ImportError) as exc:
        logger.warning("embedding provider unavailable (%s); using offline hashing", exc)
        return HashingEmbeddingProvider(dimension=settings.embedding_dimension)


@lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    return Runtime(get_settings())


def reset_runtime() -> None:
    """Clear the cached runtime (used by tests)."""
    runtime = get_runtime()
    runtime.ticket_store.clear()
    runtime.sessions.clear()
    runtime.answer_cache.clear()
    get_runtime.cache_clear()


__all__ = ["Runtime", "get_runtime", "new_session", "reset_runtime"]

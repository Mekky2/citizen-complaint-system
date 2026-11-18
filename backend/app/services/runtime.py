"""Application runtime wiring for the demo/API.

Builds the embedding provider, the knowledge base and the agents once per process. With the
default settings everything is offline (hashing embeddings + template LLM), so the API works
without API keys or a database. Configure real providers through environment variables.
"""

from __future__ import annotations

import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agents.complaint_agent.conversation import ComplaintSession, new_session
from app.agents.rag_agent.agent import RAGAgent
from app.core.config import Settings, get_settings
from app.knowledge_base.embeddings import HashingEmbeddingProvider, build_embedding_provider
from app.knowledge_base.store import InMemoryKnowledgeBase
from app.services.emergency_numbers import FileEmergencyNumbers, emergency_numbers_singleton
from app.services.offline_llm import GroundedTemplateLLM
from app.services.ticket_store import InMemoryTicketStore, ticket_store_singleton

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = {"", "changeme", "your-nvidia-nim-api-key"}


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.embedding_provider = _embedding_provider(settings)
        self.knowledge_base = InMemoryKnowledgeBase(self.embedding_provider)
        self.knowledge_stats = self._load_knowledge(settings.knowledge_dir)
        self.llm = _real_llm(settings)
        self.rag_llm: Any = self.llm or GroundedTemplateLLM()
        self.emergency_numbers: FileEmergencyNumbers = emergency_numbers_singleton()
        self.ticket_store: InMemoryTicketStore = ticket_store_singleton()
        self.sessions: dict[str, ComplaintSession] = {}
        self._lock = threading.Lock()

    def _load_knowledge(self, directory: str) -> dict[str, int]:
        path = Path(directory)
        if not path.is_absolute():
            # backend/data/knowledge regardless of the current working directory
            path = Path(__file__).resolve().parents[2] / directory
        if not path.exists():
            logger.warning("knowledge directory not found: %s", path)
            return {"inserted": 0, "updated": 0, "skipped": 0, "documents": 0}
        return self.knowledge_base.ingest_directory(str(path))

    def session(self, session_id: str) -> ComplaintSession:
        with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = new_session(
                    session_id, max_turns=self.settings.complaint_max_turns
                )
            return self.sessions[session_id]

    def rag_agent(self) -> RAGAgent:
        return RAGAgent(
            llm=self.rag_llm,
            knowledge_base=self.knowledge_base,
            embedding_provider=self.embedding_provider,
            conversation=_SimpleHistory(),
            emergency_numbers=self.emergency_numbers,
            top_k=self.settings.rag_top_k,
        )


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


def _embedding_provider(settings: Settings):
    try:
        return build_embedding_provider(settings)
    except (ValueError, ImportError) as exc:
        logger.warning("embedding provider unavailable (%s); using offline hashing", exc)
        return HashingEmbeddingProvider(dimension=settings.embedding_dimension)


def _real_llm(settings: Settings):
    if settings.llm_api_key.strip().lower() in _PLACEHOLDER_KEYS:
        return None
    try:
        from app.agents.complaint_agent.nim_client import build_llm_client

        return build_llm_client(settings)
    except Exception as exc:  # provider/config problem: stay usable offline
        logger.warning("LLM client unavailable (%s); using offline template", type(exc).__name__)
        return None


@lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    return Runtime(get_settings())


def reset_runtime() -> None:
    """Clear the cached runtime (used by tests)."""
    runtime = get_runtime()
    runtime.ticket_store.clear()
    runtime.sessions.clear()
    get_runtime.cache_clear()

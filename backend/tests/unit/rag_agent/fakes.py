"""Fake/mock implementations for RAG agent testing."""

from typing import Any

from app.agents.rag_agent.interfaces import (
    ConversationHistory,
    EmbeddingProvider,
    EmergencyNumbersProvider,
    KnowledgeBase,
)
from app.agents.rag_agent.schemas import RetrievalResult


class FakeEmbeddingProvider(EmbeddingProvider):
    """Fake embedding provider for testing."""

    def __init__(
        self,
        embedding_size: int = 1536,
        mock_vectors: dict[str, list[float]] | None = None,
    ):
        self.embedding_size = embedding_size
        self.mock_vectors = mock_vectors or {}

    def embed(self, text: str) -> list[float]:
        """Return a mock embedding."""
        if text in self.mock_vectors:
            return self.mock_vectors[text]

        # Return random mock vector
        import random

        return [random.random() for _ in range(self.embedding_size)]


class FakeKnowledgeBase(KnowledgeBase):
    """Fake knowledge base for testing.

    ``results`` lets a test script the exact retrieval outcome (e.g. ``results=[]`` for the
    "nothing relevant found" path); otherwise a small fixed ranking is returned.
    """

    def __init__(
        self,
        documents: list[dict[str, Any]] | None = None,
        results: list[RetrievalResult] | None = None,
    ):
        self.forced_results = results
        self.documents = documents or [
            {
                "id": "doc1",
                "title": "sample doc 1",
                "authority": "مديرية المياه",
                "language": "ar",
                "updated_date": "2026-01-01",
                "category": "procedures",
                "source_type": "sample",
                "content": "This is a sample document about water management.",
            },
            {
                "id": "doc2",
                "title": "sample doc 2",
                "authority": "مديرية الكهرباء",
                "language": "ar",
                "updated_date": "2026-01-01",
                "category": "procedures",
                "source_type": "sample",
                "content": "This is a sample document about electricity management.",
            },
        ]

    def ingest_document(
        self,
        file_path: str,
        title: str,
        authority: str,
        language: str,
        updated_date: str,
        category: str,
        source_type: str,
    ) -> str:
        """Mock ingestion."""
        doc_id = f"doc_{len(self.documents) + 1}"
        self.documents.append(
            {
                "id": doc_id,
                "title": title,
                "authority": authority,
                "language": language,
                "updated_date": updated_date,
                "category": category,
                "source_type": source_type,
                "content": f"Mock content for {title}",
            }
        )
        return doc_id

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.7,
        *,
        query_text: str | None = None,
    ) -> list[RetrievalResult]:
        """Mock search returning scripted results or a small fixed ranking."""
        _ = query_text
        if self.forced_results is not None:
            return [r for r in self.forced_results if r.similarity >= threshold][:top_k]
        return [
            RetrievalResult(
                document_id=f"doc{i}",
                title=f"Document {i}",
                excerpt=f"Excerpt for document {i}",
                page=None,
                similarity=0.8 - i * 0.1,
            )
            for i in range(1, min(top_k + 1, 6))
        ]

    def get_document_content(self, document_id: str) -> str | None:
        """Mock document content."""
        for doc in self.documents:
            if doc["id"] == document_id:
                return doc.get("content", "")
        return None

    def get_all_documents(self) -> list[dict[str, Any]]:
        """Mock all documents."""
        return self.documents.copy()


class FakeConversationHistory(ConversationHistory):
    """Fake conversation history for testing."""

    def __init__(self):
        self.turns = []

    def add_turn(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a turn."""
        self.turns.append({"role": role, "content": content, "metadata": metadata or {}})

    def get_recent_turns(self, n: int = 5) -> list[dict[str, Any]]:
        """Get recent turns."""
        return self.turns[-n:]

    def clear(self) -> None:
        """Clear conversation."""
        self.turns = []


class FakeEmergencyNumbers(EmergencyNumbersProvider):
    """Fake emergency numbers provider."""

    def get_numbers_by_category(self, category: str) -> list[dict[str, Any]]:
        """Mock emergency numbers by category."""
        return [
            {
                "id": "police",
                "category": "emergency",
                "name": "Police",
                "number": "122",
                "description": "Police emergency",
            },
            {
                "id": "ambulance",
                "category": "emergency",
                "name": "Ambulance",
                "number": "123",
                "description": "Medical emergency",
            },
        ]

    def get_all_numbers(self) -> list[dict[str, Any]]:
        """Mock all emergency numbers."""
        return [
            {
                "id": "police",
                "category": "emergency",
                "name": "Police",
                "number": "122",
                "description": "Police emergency",
            },
            {
                "id": "ambulance",
                "category": "emergency",
                "name": "Ambulance",
                "number": "123",
                "description": "Medical emergency",
            },
            {
                "id": "fire",
                "category": "emergency",
                "name": "Fire",
                "number": "180",
                "description": "Fire emergency",
            },
        ]


class FakeLLM:
    """Fake LLM client for testing."""

    def __init__(self, answer: str = "Hello, this is a test answer."):
        self.calls = []
        self.answer = answer

    def complete(self, system: str, user: str) -> str:
        """Return a mock answer."""
        self.calls.append((system, user))
        return self.answer

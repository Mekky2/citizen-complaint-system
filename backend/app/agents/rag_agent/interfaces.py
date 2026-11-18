"""Interfaces between the RAG Agent and the outside world."""

from typing import Any, Protocol

from app.agents.rag_agent.schemas import RetrievalResult


class EmbeddingProvider(Protocol):
    """Protocol for embedding generation."""

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding for text.

        Args:
            text: Input text (already normalized for embedding search)

        Returns:
            Embedding vector.
        """
        ...


class KnowledgeBase(Protocol):
    """Protocol for knowledge base operations."""

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
        """
        Ingest a document into the knowledge base.

        Args:
            file_path: Path to the document file.
            title: Document title.
            authority: Authority responsible for this document.
            language: Language code (e.g., 'ar').
            updated_date: Last updated date (ISO format).
            category: Category of the document.
            source_type: Type of content ('sample', 'official', etc.).

        Returns:
            Document ID.
        """
        ...

    def search(
        self, query_embedding: list[float], top_k: int = 5, threshold: float = 0.7
    ) -> list[RetrievalResult]:
        """
        Search the knowledge base for relevant documents.

        Args:
            query_embedding: Embedding of the normalized query.
            top_k: Maximum number of results to return.
            threshold: Minimum similarity threshold (0.0-1.0).

        Returns:
            List of retrieval results, sorted by similarity descending.
        """
        ...

    def get_document_content(self, document_id: str) -> str | None:
        """
        Get the original full content of a document.

        Args:
            document_id: Document ID.

        Returns:
            Full document content, or None if not found.
        """
        ...

    def get_all_documents(self) -> list[dict[str, Any]]:
        """
        Get all documents (for ingestion scripts).

        Returns:
            List of document metadata.
        """
        ...


class ConversationHistory(Protocol):
    """Protocol for managing conversation history."""

    def add_turn(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """
        Add a turn to the conversation history.

        Args:
            role: 'user' or 'assistant'.
            content: Message content.
            metadata: Additional metadata.
        """
        ...

    def get_recent_turns(self, n: int = 5) -> list[dict[str, Any]]:
        """
        Get the most recent N turns.

        Args:
            n: Number of recent turns.

        Returns:
            List of recent turns.
        """
        ...

    def clear(self) -> None:
        """Clear the conversation history."""
        ...


class EmergencyNumbersProvider(Protocol):
    """Protocol for accessing emergency numbers."""

    def get_numbers_by_category(self, category: str) -> list[dict[str, Any]]:
        """
        Get emergency numbers by category.

        Args:
            category: Category name (e.g., 'emergency', 'non-emergency').

        Returns:
            List of emergency numbers.
        """
        ...

    def get_all_numbers(self) -> list[dict[str, Any]]:
        """
        Get all emergency numbers.

        Returns:
            List of all emergency numbers.
        """
        ...

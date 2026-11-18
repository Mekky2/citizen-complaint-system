"""Adapter from the orchestrator's ``RagRetriever`` protocol to our hybrid knowledge base.

The teammate's complaint agent only needs ``retrieve(query, category, top_k) -> list`` with
``source`` and ``excerpt`` keys. This class fills that contract using the Arabic-normalizing,
hybrid BM25 + vector store, so the structured agent and the RAG agent read the same documents.
"""

from __future__ import annotations

from typing import Any

from app.utils.arabic_normalizer import normalize_arabic

MAX_QUERY_CHARS = 500


class KnowledgeBaseRetriever:
    def __init__(self, knowledge_base: Any, *, threshold: float | None = None):
        self.kb = knowledge_base
        self.threshold = threshold

    def _threshold(self) -> float:
        if self.threshold is not None:
            return self.threshold
        return float(getattr(self.kb.embedding_provider, "default_threshold", 0.15))

    def retrieve(self, query: str, category: str = "", top_k: int = 5) -> list[dict[str, str]]:
        """Return ``[{"source": title, "excerpt": text}]`` best first.

        A category match only reorders results; it never hides a relevant document from
        another category, because the agent explicitly forbids inventing recommendations.
        """
        text = normalize_arabic(query or "")[:MAX_QUERY_CHARS]
        if not text.strip():
            return []
        embedding = self.kb.embedding_provider.embed(text)
        results = self.kb.search(
            embedding,
            top_k=max(1, top_k),
            threshold=self._threshold(),
            query_text=text,
        )
        ordered = list(results)
        if category:
            ordered.sort(
                key=lambda item: self._category(item.document_id) != category
            )
        return [
            {"source": item.title, "excerpt": item.excerpt}
            for item in ordered
            if item.title and item.excerpt
        ][: max(1, top_k)]

    def _category(self, document_id: str) -> str:
        documents = getattr(self.kb, "documents", {}) or {}
        for document in documents.values():
            if document.get("id") == document_id:
                return str(document.get("category") or "")
        return ""


__all__ = ["KnowledgeBaseRetriever"]

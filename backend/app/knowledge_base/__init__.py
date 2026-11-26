"""Knowledge-base package: loading, Arabic-aware chunking, embeddings and stores."""

from app.knowledge_base.chunking import TextChunk, chunk_text, estimate_tokens
from app.knowledge_base.embeddings import (
    HashingEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    build_embedding_provider,
)
from app.knowledge_base.loaders import KnowledgeDocument, iter_documents, load_document
from app.knowledge_base.store import InMemoryKnowledgeBase, PgVectorKnowledgeBase

__all__ = [
    "HashingEmbeddingProvider",
    "InMemoryKnowledgeBase",
    "KnowledgeDocument",
    "OpenAICompatibleEmbeddingProvider",
    "PgVectorKnowledgeBase",
    "TextChunk",
    "build_embedding_provider",
    "chunk_text",
    "estimate_tokens",
    "iter_documents",
    "load_document",
]

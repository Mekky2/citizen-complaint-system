"""
Models for: legal_knowledge_documents, legal_knowledge_chunks, ticket_embeddings
(database/init/03_tables.sql, sections 4-5 — the Legal RAG vs Similar-Case split).

embedding columns use pgvector's Vector type with NO dimension argument
(Vector(), not Vector(1536)) — this matches the database exactly: the
columns are an unconstrained `vector` type until the AI team's embedding
model is finalized (see database/init/04_indexes.sql for the documented
migration path once it is). Passing a dimension here would make SQLAlchemy's
own type checking fight a column that is deliberately flexible.
"""

import uuid

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import LegalSourceType, pg_enum
from app.models.mixins import TimestampMixin, UpdatedAtMixin, UUIDPKMixin

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - only hit if pgvector isn't installed yet
    Vector = None  # type: ignore[assignment,misc]


class LegalKnowledgeDocument(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "legal_knowledge_documents"

    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[LegalSourceType] = mapped_column(
        pg_enum(LegalSourceType, "legal_source_type_enum"), nullable=False
    )
    reference_number: Mapped[str | None] = mapped_column(Text)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    published_date: Mapped["object"] = mapped_column(Date, nullable=True)


class LegalKnowledgeChunk(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "legal_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index", name="legal_knowledge_chunks_doc_chunk_unique"
        ),
        CheckConstraint(
            "embedding IS NULL OR embedding_dim IS NULL OR vector_dims(embedding) = embedding_dim",
            name="legal_knowledge_chunks_dim_check",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_dim: Mapped[int | None] = mapped_column(Integer)


class TicketEmbedding(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "ticket_embeddings"
    __table_args__ = (
        CheckConstraint(
            "embedding IS NULL OR embedding_dim IS NULL OR vector_dims(embedding) = embedding_dim",
            name="ticket_embeddings_dim_check",
        ),
    )

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_dim: Mapped[int | None] = mapped_column(Integer)

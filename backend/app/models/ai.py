"""
Models for: ai_runs, ai_tool_calls, ai_recommendations, ai_evidence,
supervisor_decisions (database/init/03_tables.sql, section 6).

ai_evidence.__table_args__ carries the CHECK constraint that is the actual
enforcement of "Legal RAG vs Similar Cases must remain separate" — a row can
only be LEGAL_EVIDENCE (-> legal_knowledge_chunks) or SIMILAR_CASE
(-> tickets), never both, never neither. The service layer in
app/services/evidence.py builds rows that satisfy this by construction, but
the constraint is what actually guarantees it, even against a bug.
"""
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import AiEvidenceType, AiRunStatus, DecisionAction, Severity, pg_enum
from app.models.mixins import TimestampMixin, UpdatedAtMixin, UUIDPKMixin


class AiRun(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "ai_runs"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[AiRunStatus] = mapped_column(
        pg_enum(AiRunStatus, "ai_run_status_enum"), nullable=False, server_default=text("'pending'")
    )
    model_provider: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped["object"] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped["object"] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text)


class AiToolCall(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "ai_tool_calls"

    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class AiRecommendation(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "ai_recommendations"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ai_recommendations_confidence_check",
        ),
    )

    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    severity: Mapped[Severity | None] = mapped_column(pg_enum(Severity, "severity_enum"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT")
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    explanation: Mapped[str | None] = mapped_column(Text)
    factors: Mapped[dict | None] = mapped_column(JSONB)


class AiEvidence(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "ai_evidence"
    __table_args__ = (
        CheckConstraint(
            "(evidence_type = 'LEGAL_EVIDENCE' AND knowledge_chunk_id IS NOT NULL AND cited_ticket_id IS NULL) "
            "OR (evidence_type = 'SIMILAR_CASE' AND cited_ticket_id IS NOT NULL AND knowledge_chunk_id IS NULL)",
            name="ai_evidence_type_source_check",
        ),
        CheckConstraint(
            "similarity_score IS NULL OR (similarity_score >= 0 AND similarity_score <= 1)",
            name="ai_evidence_similarity_check",
        ),
    )

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_recommendations.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[AiEvidenceType] = mapped_column(
        pg_enum(AiEvidenceType, "ai_evidence_type_enum"), nullable=False
    )
    knowledge_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_knowledge_chunks.id", ondelete="RESTRICT")
    )
    cited_ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="RESTRICT")
    )
    snippet: Mapped[str | None] = mapped_column(Text)
    similarity_score: Mapped[float | None] = mapped_column(Numeric(5, 4))


class SupervisorDecision(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "supervisor_decisions"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_recommendations.id", ondelete="RESTRICT")
    )
    supervisor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[DecisionAction] = mapped_column(pg_enum(DecisionAction, "decision_action_enum"), nullable=False)
    changed_fields: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)

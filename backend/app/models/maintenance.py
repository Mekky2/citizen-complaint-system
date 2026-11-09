"""Models for: maintenance_tasks, task_evidence, verifications (database/init/03_tables.sql, section 7)."""
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import MediaType, TaskStatus, VerificationResult, pg_enum
from app.models.mixins import TimestampMixin, UpdatedAtMixin, UUIDPKMixin


class MaintenanceTask(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "maintenance_tasks"
    __table_args__ = (
        UniqueConstraint("ticket_id", "attempt_number", name="maintenance_tasks_ticket_attempt_unique"),
        CheckConstraint("attempt_number >= 1", name="maintenance_tasks_attempt_positive_check"),
    )

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_teams.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    status: Mapped[TaskStatus] = mapped_column(
        pg_enum(TaskStatus, "task_status_enum"), nullable=False, server_default=text("'assigned'")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    assigned_at: Mapped["object"] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    started_at: Mapped["object"] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped["object"] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskEvidence(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "task_evidence"
    __table_args__ = (CheckConstraint("stage IN ('progress', 'after')", name="task_evidence_stage_check"),)

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[MediaType] = mapped_column(pg_enum(MediaType, "media_type_enum"), nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'after'"))
    url: Mapped[str] = mapped_column(Text, nullable=False)


class Verification(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "verifications"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    verifier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    result: Mapped[VerificationResult] = mapped_column(
        pg_enum(VerificationResult, "verification_result_enum"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)

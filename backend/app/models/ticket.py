"""Models for: tickets, ticket_media, ticket_status_history (database/init/03_tables.sql, section 3)."""
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import MediaType, Severity, TicketStatus, pg_enum
from app.models.mixins import TimestampMixin, UpdatedAtMixin, UUIDPKMixin


class Ticket(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("lat BETWEEN -90 AND 90", name="tickets_lat_check"),
        CheckConstraint("lng BETWEEN -180 AND 180", name="tickets_lng_check"),
    )

    citizen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT")
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT")
    )
    severity: Mapped[Severity | None] = mapped_column(pg_enum(Severity, "severity_enum"))
    status: Mapped[TicketStatus] = mapped_column(
        pg_enum(TicketStatus, "ticket_status_enum"), nullable=False, server_default=text("'submitted'")
    )
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(nullable=False)
    lng: Mapped[float] = mapped_column(nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    governorate: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)

    media: Mapped[list["TicketMedia"]] = relationship(back_populates="ticket")
    status_history: Mapped[list["TicketStatusHistory"]] = relationship(back_populates="ticket")


class TicketMedia(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "ticket_media"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[MediaType] = mapped_column(pg_enum(MediaType, "media_type_enum"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="media")


class TicketStatusHistory(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "ticket_status_history"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[TicketStatus | None] = mapped_column(pg_enum(TicketStatus, "ticket_status_enum"))
    to_status: Mapped[TicketStatus] = mapped_column(pg_enum(TicketStatus, "ticket_status_enum"), nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(Text)

    ticket: Mapped["Ticket"] = relationship(back_populates="status_history")

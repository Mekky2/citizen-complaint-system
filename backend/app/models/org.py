"""Models for: departments, maintenance_teams, maintenance_team_members, categories
(database/init/03_tables.sql, sections 2-3)."""

import uuid

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin, UpdatedAtMixin, UUIDPKMixin


class Department(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class MaintenanceTeam(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "maintenance_teams"
    __table_args__ = (
        UniqueConstraint("department_id", "name", name="maintenance_teams_dept_name_unique"),
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    members: Mapped[list["MaintenanceTeamMember"]] = relationship(back_populates="team")


class MaintenanceTeamMember(Base):
    __tablename__ = "maintenance_team_members"

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maintenance_teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped["object"] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    team: Mapped["MaintenanceTeam"] = relationship(back_populates="members")


class Category(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    default_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL")
    )

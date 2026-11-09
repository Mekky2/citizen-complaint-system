"""Models for: users, roles, user_roles (database/init/03_tables.sql, section 1)."""

import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin, UpdatedAtMixin, UUIDPKMixin


class User(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    phone: Mapped[str | None] = mapped_column(Text, unique=True)
    national_id: Mapped[str | None] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    deactivated_at: Mapped["object"] = mapped_column(DateTime(timezone=True), nullable=True)

    role_links: Mapped[list["UserRole"]] = relationship(back_populates="user")


class Role(Base, UUIDPKMixin, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped["object"] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    user: Mapped["User"] = relationship(back_populates="role_links")
    role: Mapped["Role"] = relationship()

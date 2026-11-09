"""
Shared column mixins matching the convention stated at the top of
database/init/03_tables.sql:

    id UUID PRIMARY KEY DEFAULT gen_random_uuid()
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()   -- only on editable tables

server_default=text("gen_random_uuid()") / text("now()") means Postgres
generates these values (exactly as the SQL files specify), not Python — the
backend never has to guess a default that might drift from the database.
"""

import uuid

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class TimestampMixin:
    created_at: Mapped["object"] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class UpdatedAtMixin:
    """Only mixed into tables that actually have updated_at (see 03_tables.sql comments)."""

    updated_at: Mapped["object"] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

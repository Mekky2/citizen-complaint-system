"""Shared Pydantic building blocks used across every schema module."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """Base for any schema read directly off a SQLAlchemy model instance."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedOut(ORMBase):
    id: UUID
    created_at: datetime


class Page(BaseModel):
    """Generic pagination envelope used by list endpoints."""

    total: int
    limit: int
    offset: int

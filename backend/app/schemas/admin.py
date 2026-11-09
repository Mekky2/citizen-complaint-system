"""Schemas for /api/v1/admin — departments, categories, audit log reads."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class DepartmentCreateIn(BaseModel):
    name: str = Field(min_length=2)
    description: str | None = None


class DepartmentOut(ORMBase):
    id: UUID
    name: str
    description: str | None


class CategoryCreateIn(BaseModel):
    name: str = Field(min_length=2)
    default_department_id: UUID | None = None


class CategoryOut(ORMBase):
    id: UUID
    name: str
    default_department_id: UUID | None


class AuditLogOut(ORMBase):
    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID
    before: dict | None
    after: dict | None
    created_at: datetime

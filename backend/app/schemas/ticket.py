"""Schemas for /api/v1/tickets."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import MediaType, Severity, TicketStatus
from app.schemas.common import ORMBase


class TicketCreateIn(BaseModel):
    description: str = Field(min_length=10)
    title: str | None = None
    lat: float
    lng: float
    address: str | None = None
    governorate: str | None = None
    city: str | None = None
    category_id: UUID | None = None  # optional citizen hint; AI/supervisor may override

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("lng must be between -180 and 180")
        return v


class TicketMediaOut(ORMBase):
    id: UUID
    type: MediaType
    url: str
    created_at: datetime


class TicketMediaCreateIn(BaseModel):
    """Metadata only — the file itself is uploaded directly to object storage by the
    frontend; the backend never receives or stores binary content (see README)."""

    type: MediaType
    url: str


class TicketStatusHistoryOut(ORMBase):
    id: UUID
    from_status: TicketStatus | None
    to_status: TicketStatus
    changed_by: UUID | None
    reason: str | None
    created_at: datetime


class TicketOut(ORMBase):
    id: UUID
    citizen_id: UUID
    category_id: UUID | None
    department_id: UUID | None
    severity: Severity | None
    status: TicketStatus
    title: str | None
    description: str
    lat: float
    lng: float
    address: str | None
    governorate: str | None
    city: str | None
    created_at: datetime
    updated_at: datetime


class TicketDetailOut(TicketOut):
    media: list[TicketMediaOut] = []
    status_history: list[TicketStatusHistoryOut] = []

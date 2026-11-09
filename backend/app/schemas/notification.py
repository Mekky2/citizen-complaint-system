"""Schemas for /api/v1/notifications."""
from datetime import datetime
from uuid import UUID

from app.models.enums import NotificationChannel
from app.schemas.common import ORMBase


class NotificationOut(ORMBase):
    id: UUID
    ticket_id: UUID | None
    channel: NotificationChannel
    title: str
    body: str | None
    read_at: datetime | None
    created_at: datetime

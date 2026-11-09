"""
Business logic for /api/v1/notifications.

create_notification() is used internally by other services (ticket status
changes, AI run completion, supervisor decisions) — it is not itself exposed
as a public "create" endpoint; the router only lets a user list and mark-read
their OWN notifications, never create one for anybody, including themselves.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import NotificationChannel
from app.models.system import Notification


def create_notification(
    db: Session,
    *,
    user_id: uuid.UUID,
    title: str,
    body: str | None = None,
    ticket_id: uuid.UUID | None = None,
    channel: NotificationChannel = NotificationChannel.in_app,
) -> Notification:
    notification = Notification(user_id=user_id, ticket_id=ticket_id, channel=channel, title=title, body=body)
    db.add(notification)
    return notification


def list_notifications(
    db: Session, user_id: uuid.UUID, *, unread_only: bool, limit: int, offset: int
) -> tuple[list[Notification], int]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    total = query.count()
    rows = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset).all()
    return rows, total


def mark_notification_read(db: Session, notification_id: uuid.UUID, *, user_id: uuid.UUID) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification

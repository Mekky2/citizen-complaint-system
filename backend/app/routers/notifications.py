"""GET/PATCH /api/v1/notifications/* — a user's own notifications only."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import CurrentUser, get_current_user
from app.schemas.notification import NotificationOut
from app.services import notifications as notifications_service

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NotificationOut]:
    rows, _total = notifications_service.list_notifications(
        db, current_user.id, unread_only=unread_only, limit=limit, offset=offset
    )
    return rows


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationOut:
    return notifications_service.mark_notification_read(db, notification_id, user_id=current_user.id)

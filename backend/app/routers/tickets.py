"""/api/v1/tickets/* — citizen-created tickets, their media, and status history.

Visibility rule enforced in every handler below: a citizen sees only their
own tickets; any staff role (supervisor/technician/admin) sees all of them.
Creating a ticket is citizen-only — staff never file a ticket as themselves.
"""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from app.db import get_db
from app.dependencies.auth import CurrentUser, get_current_user, require_role
from app.models.enums import MediaType, TicketStatus
from app.models.ticket import TicketMedia
from app.schemas.ticket import (
    TicketCreateIn,
    TicketDetailOut,
    TicketMediaCreateIn,
    TicketMediaOut,
    TicketOut,
)
from app.services import tickets as tickets_service
from app.services.media_storage import (
    save_upload,
    find_media_file,
    get_media_content_type,
)

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


def _assert_can_view(ticket, current_user: CurrentUser) -> None:
    if current_user.role == "citizen" and ticket.citizen_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This is not your ticket")


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreateIn,
    current_user: CurrentUser = Depends(require_role("citizen")),
    db: Session = Depends(get_db),
) -> TicketOut:
    return tickets_service.create_ticket(db, payload, citizen_id=current_user.id)


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TicketOut]:
    citizen_id = current_user.id if current_user.role == "citizen" else None
    tickets, _total = tickets_service.list_tickets(
        db, citizen_id=citizen_id, status_filter=status_filter, limit=limit, offset=offset
    )
    return tickets


@router.get("/{ticket_id}", response_model=TicketDetailOut)
def get_ticket(
    ticket_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketDetailOut:
    ticket = tickets_service.get_ticket(db, ticket_id, with_details=True)
    _assert_can_view(ticket, current_user)
    return ticket


@router.post(
    "/{ticket_id}/media", response_model=TicketMediaOut, status_code=status.HTTP_201_CREATED
)
def add_ticket_media(
    ticket_id: uuid.UUID,
    payload: TicketMediaCreateIn,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketMediaOut:
    ticket = tickets_service.get_ticket(db, ticket_id)
    _assert_can_view(ticket, current_user)
    return tickets_service.add_ticket_media(db, ticket_id, payload, actor_id=current_user.id)


@router.post(
    "/{ticket_id}/media/upload",
    response_model=TicketMediaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_ticket_media(
    ticket_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketMediaOut:
    ticket = tickets_service.get_ticket(db, ticket_id)
    _assert_can_view(ticket, current_user)

    media_id = uuid.uuid4()
    saved_path = None

    try:
        media_type, saved_path = await save_upload(file, ticket_id, media_id)

        payload = TicketMediaCreateIn(
            type=MediaType(media_type),
            url=f"/api/v1/tickets/media/{media_id}",
        )

        return tickets_service.add_ticket_media(
            db,
            ticket_id,
            payload,
            actor_id=current_user.id,
            media_id=media_id,
        )
    except Exception:
        if saved_path is not None:
            saved_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.get("/media/{media_id}")
def get_ticket_media(
    media_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    media = db.query(TicketMedia).filter(TicketMedia.id == media_id).first()

    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    ticket = tickets_service.get_ticket(db, media.ticket_id)
    _assert_can_view(ticket, current_user)

    path = find_media_file(ticket.id, media.id)
    if path is None:
        raise HTTPException(status_code=404, detail="Media file not found")

    return FileResponse(
        path=path,
        media_type=get_media_content_type(path),
        headers={
            "Content-Disposition": f'inline; filename="{path.name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )

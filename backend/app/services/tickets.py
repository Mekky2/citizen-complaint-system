"""
Business logic for /api/v1/tickets: creation, media, reads, and the one
status-transition helper every other service (supervisor, maintenance,
verification, ai) composes into its own transaction.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.models.enums import TicketStatus
from app.models.ticket import Ticket, TicketMedia, TicketStatusHistory
from app.schemas.ticket import TicketCreateIn, TicketMediaCreateIn
from app.services.common import write_audit_log


def create_ticket(db: Session, payload: TicketCreateIn, *, citizen_id: uuid.UUID) -> Ticket:
    ticket = Ticket(
        citizen_id=citizen_id,
        category_id=payload.category_id,
        title=payload.title,
        description=payload.description,
        lat=payload.lat,
        lng=payload.lng,
        address=payload.address,
        governorate=payload.governorate,
        city=payload.city,
    )
    db.add(ticket)
    db.flush()

    db.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=None,
            to_status=TicketStatus.submitted,
            changed_by=citizen_id,
            reason="Ticket created",
        )
    )
    write_audit_log(
        db, actor_id=citizen_id, action="create_ticket", entity_type="ticket", entity_id=ticket.id
    )

    db.commit()
    db.refresh(ticket)
    return ticket


def get_ticket(db: Session, ticket_id: uuid.UUID, *, with_details: bool = False) -> Ticket:
    query = db.query(Ticket)
    if with_details:
        query = query.options(selectinload(Ticket.media), selectinload(Ticket.status_history))
    ticket = query.filter(Ticket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def list_tickets(
    db: Session,
    *,
    citizen_id: uuid.UUID | None,
    status_filter: TicketStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Ticket], int]:
    query = db.query(Ticket)
    if citizen_id is not None:
        query = query.filter(Ticket.citizen_id == citizen_id)
    if status_filter is not None:
        query = query.filter(Ticket.status == status_filter)
    total = query.count()
    rows = query.order_by(Ticket.created_at.desc()).limit(limit).offset(offset).all()
    return rows, total


def add_ticket_media(
    db: Session,
    ticket_id: uuid.UUID,
    payload: TicketMediaCreateIn,
    *,
    actor_id: uuid.UUID,
    media_id: uuid.UUID | None = None,
) -> TicketMedia:
    ticket = get_ticket(db, ticket_id)
    media = TicketMedia(
        id=media_id,
        ticket_id=ticket.id,
        type=payload.type,
        url=payload.url,
    )
    db.add(media)
    write_audit_log(
        db,
        actor_id=actor_id,
        action="add_ticket_media",
        entity_type="ticket",
        entity_id=ticket.id,
        after={"media_type": payload.type.value, "url": payload.url},
    )
    db.commit()
    db.refresh(media)
    return media


def transition_ticket_status(
    db: Session,
    ticket: Ticket,
    *,
    to_status: TicketStatus,
    changed_by: uuid.UUID | None,
    reason: str | None = None,
) -> Ticket:
    """
    The single place a ticket's status field changes. Every caller (supervisor
    decisions, maintenance task creation/updates, verification, AI run
    callbacks) composes this into its own transaction rather than committing
    here, so the status change and the row(s) that caused it land together —
    ticket_status_history is always a complete, ordered trail with no gaps.
    """
    from_status = ticket.status
    ticket.status = to_status
    db.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            reason=reason,
        )
    )
    return ticket

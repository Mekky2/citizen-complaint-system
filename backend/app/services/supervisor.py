"""
Business logic for /api/v1/supervisor — the human-in-the-loop approval gate.

A ticket can only leave 'awaiting_approval' through a SupervisorDecision row.
The AI never moves a ticket past this state on its own, no matter how
confident the recommendation (app/services/ai.py stops at 'awaiting_approval'
on success) — submit_decision() is the one and only place a ticket advances
past it, whether the supervisor approves, edits, or rejects.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.ai import AiRecommendation, SupervisorDecision
from app.models.enums import DecisionAction, TicketStatus
from app.schemas.supervisor import SupervisorDecisionIn
from app.services.common import write_audit_log
from app.services.tickets import get_ticket, transition_ticket_status


def submit_decision(
    db: Session, ticket_id: uuid.UUID, payload: SupervisorDecisionIn, *, supervisor_id: uuid.UUID
) -> SupervisorDecision:
    ticket = get_ticket(db, ticket_id)
    if ticket.status != TicketStatus.awaiting_approval:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket is '{ticket.status.value}', not 'awaiting_approval' — no decision is pending",
        )

    recommendation = (
        db.query(AiRecommendation)
        .filter(AiRecommendation.ticket_id == ticket.id)
        .order_by(AiRecommendation.created_at.desc())
        .first()
    )

    changed_fields: dict = {}

    if payload.action in (DecisionAction.approve, DecisionAction.edit):
        category_id = payload.category_id_override or (
            recommendation.category_id if recommendation else None
        )
        department_id = payload.department_id_override or (
            recommendation.department_id if recommendation else None
        )
        severity = payload.severity_override or (
            recommendation.severity if recommendation else None
        )

        if payload.action == DecisionAction.edit:
            if payload.category_id_override:
                changed_fields["category_id"] = str(payload.category_id_override)
            if payload.department_id_override:
                changed_fields["department_id"] = str(payload.department_id_override)
            if payload.severity_override:
                changed_fields["severity"] = payload.severity_override.value

        ticket.category_id = category_id
        ticket.department_id = department_id
        ticket.severity = severity
        transition_ticket_status(
            db,
            ticket,
            to_status=TicketStatus.assigned,
            changed_by=supervisor_id,
            reason=f"Supervisor {payload.action.value}d the AI recommendation",
        )
    else:  # reject
        transition_ticket_status(
            db,
            ticket,
            to_status=TicketStatus.rejected,
            changed_by=supervisor_id,
            reason=payload.reason,
        )

    decision = SupervisorDecision(
        ticket_id=ticket.id,
        recommendation_id=recommendation.id if recommendation else None,
        supervisor_id=supervisor_id,
        action=payload.action,
        changed_fields=changed_fields or None,
        reason=payload.reason,
    )
    db.add(decision)
    write_audit_log(
        db,
        actor_id=supervisor_id,
        action="supervisor_decision",
        entity_type="ticket",
        entity_id=ticket.id,
        after={"action": payload.action.value},
    )

    db.commit()
    db.refresh(decision)
    return decision

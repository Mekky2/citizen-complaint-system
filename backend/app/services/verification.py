"""
Business logic for /api/v1/verification — a supervisor verifies a completed
maintenance task:
  - 'pass'  -> task completed, ticket completed.
  - 'fail'  -> this task attempt is still marked completed (it IS finished,
    just unsuccessfully), and the ticket goes back to 'assigned' so
    app/services/maintenance.py:create_maintenance_task can open the next
    rework attempt (attempt_number + 1) against it.
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import TaskStatus, TicketStatus, VerificationResult
from app.models.maintenance import MaintenanceTask, Verification
from app.schemas.maintenance import VerificationCreateIn
from app.services.common import write_audit_log
from app.services.tickets import get_ticket, transition_ticket_status


def create_verification(
    db: Session, task_id: uuid.UUID, payload: VerificationCreateIn, *, verifier_id: uuid.UUID
) -> Verification:
    task = db.get(MaintenanceTask, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance task not found")
    if task.status != TaskStatus.pending_verification:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is '{task.status.value}', not 'pending_verification'",
        )

    verification = Verification(task_id=task.id, verifier_id=verifier_id, result=payload.result, note=payload.note)
    db.add(verification)

    ticket = get_ticket(db, task.ticket_id)
    task.status = TaskStatus.completed  # this attempt is finished either way

    if payload.result == VerificationResult.pass_:
        transition_ticket_status(
            db, ticket, to_status=TicketStatus.completed, changed_by=verifier_id, reason="Verification passed",
        )
    else:
        transition_ticket_status(
            db, ticket, to_status=TicketStatus.assigned, changed_by=verifier_id,
            reason=f"Verification failed ({payload.note or 'no note'}) — sent back for rework",
        )

    write_audit_log(
        db, actor_id=verifier_id, action="create_verification", entity_type="maintenance_task", entity_id=task.id,
        after={"result": payload.result.value},
    )

    db.commit()
    db.refresh(verification)
    return verification

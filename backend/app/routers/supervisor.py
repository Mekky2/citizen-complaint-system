"""POST /api/v1/supervisor/* — the human-approval gate. Supervisor-only."""
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import CurrentUser, require_role
from app.schemas.supervisor import SupervisorDecisionIn, SupervisorDecisionOut
from app.services import supervisor as supervisor_service

router = APIRouter(prefix="/api/v1/supervisor", tags=["supervisor"])


@router.post(
    "/tickets/{ticket_id}/decisions", response_model=SupervisorDecisionOut, status_code=status.HTTP_201_CREATED
)
def submit_decision(
    ticket_id: uuid.UUID,
    payload: SupervisorDecisionIn,
    current_user: CurrentUser = Depends(require_role("supervisor", "admin")),
    db: Session = Depends(get_db),
) -> SupervisorDecisionOut:
    return supervisor_service.submit_decision(db, ticket_id, payload, supervisor_id=current_user.id)

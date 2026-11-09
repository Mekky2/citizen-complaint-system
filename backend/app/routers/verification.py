"""POST /api/v1/verification/* — supervisor verifies a completed maintenance task."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import CurrentUser, require_role
from app.schemas.maintenance import VerificationCreateIn, VerificationOut
from app.services import verification as verification_service

router = APIRouter(prefix="/api/v1/verification", tags=["verification"])


@router.post(
    "/tasks/{task_id}", response_model=VerificationOut, status_code=status.HTTP_201_CREATED
)
def create_verification(
    task_id: uuid.UUID,
    payload: VerificationCreateIn,
    current_user: CurrentUser = Depends(require_role("supervisor", "admin")),
    db: Session = Depends(get_db),
) -> VerificationOut:
    return verification_service.create_verification(
        db, task_id, payload, verifier_id=current_user.id
    )

"""
/api/v1/maintenance/* — teams, team membership (technician-only, enforced in
app/services/maintenance.py), task assignment/rework, task status updates,
and task evidence.

Every endpoint below that touches a SPECIFIC, already-identified task
(status update, evidence add/list) passes actor_role through to the service
layer, which calls _assert_can_access_task() — a technician only gets past
that check if they are a member of the task's own maintenance team, not just
any technician who happens to know the task_id. See
app/services/maintenance.py module docstring for the full rationale.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies.auth import CurrentUser, get_current_user, require_role
from app.schemas.maintenance import (
    MaintenanceTaskCreateIn,
    MaintenanceTaskOut,
    MaintenanceTaskStatusUpdateIn,
    MaintenanceTeamCreateIn,
    MaintenanceTeamMemberAddIn,
    MaintenanceTeamMemberOut,
    MaintenanceTeamOut,
    TaskEvidenceCreateIn,
    TaskEvidenceOut,
)
from app.services import maintenance as maintenance_service

router = APIRouter(prefix="/api/v1/maintenance", tags=["maintenance"])


@router.post(
    "/teams",
    response_model=MaintenanceTeamOut,
    status_code=status.HTTP_201_CREATED,
)
def create_team(
    payload: MaintenanceTeamCreateIn,
    current_user: CurrentUser = Depends(
        require_role("admin", "supervisor")
    ),
    db: Session = Depends(get_db),
) -> MaintenanceTeamOut:
    return maintenance_service.create_team(
        db,
        payload,
        actor_id=current_user.id,
    )


@router.get("/teams", response_model=list[MaintenanceTeamOut])
def list_teams(
    department_id: uuid.UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(
        require_role("admin", "supervisor", "technician")
    ),
    db: Session = Depends(get_db),
) -> list[MaintenanceTeamOut]:
    return maintenance_service.list_teams(
        db,
        department_id=department_id,
    )


@router.get(
    "/teams/{team_id}/members",
    response_model=list[MaintenanceTeamMemberOut],
)
def list_team_members(
    team_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role("admin", "supervisor")
    ),
    db: Session = Depends(get_db),
) -> list[MaintenanceTeamMemberOut]:
    return maintenance_service.list_team_members(
        db,
        team_id,
    )


@router.post(
    "/teams/{team_id}/members",
    status_code=status.HTTP_201_CREATED,
)
def add_team_member(
    team_id: uuid.UUID,
    payload: MaintenanceTeamMemberAddIn,
    current_user: CurrentUser = Depends(
        require_role("admin", "supervisor")
    ),
    db: Session = Depends(get_db),
) -> dict:
    maintenance_service.add_team_member(
        db,
        team_id,
        payload.user_id,
        actor_id=current_user.id,
    )
    return {
        "team_id": str(team_id),
        "user_id": str(payload.user_id),
        "status": "added",
    }


@router.post(
    "/tickets/{ticket_id}/tasks",
    response_model=MaintenanceTaskOut,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    ticket_id: uuid.UUID,
    payload: MaintenanceTaskCreateIn,
    current_user: CurrentUser = Depends(
        require_role("admin", "supervisor")
    ),
    db: Session = Depends(get_db),
) -> MaintenanceTaskOut:
    return maintenance_service.create_maintenance_task(
        db,
        ticket_id,
        payload,
        assigned_by=current_user.id,
    )


@router.get(
    "/tickets/{ticket_id}/tasks",
    response_model=list[MaintenanceTaskOut],
)
def list_tasks_for_ticket(
    ticket_id: uuid.UUID,
    current_user: CurrentUser = Depends(
        require_role("admin", "supervisor")
    ),
    db: Session = Depends(get_db),
) -> list[MaintenanceTaskOut]:
    return maintenance_service.list_tasks_for_ticket(
        db,
        ticket_id,
    )


@router.get(
    "/tasks/mine",
    response_model=list[MaintenanceTaskOut],
)
def list_my_tasks(
    current_user: CurrentUser = Depends(
        require_role("technician")
    ),
    db: Session = Depends(get_db),
) -> list[MaintenanceTaskOut]:
    """Every task belonging to any team this technician is a member of —
    the 'My Tasks' view, and the intended way a technician discovers task IDs
    at all, rather than guessing or being handed one for a task outside their
    team.
    """
    return maintenance_service.list_tasks_for_user_teams(
        db,
        current_user.id,
    )


@router.patch(
    "/tasks/{task_id}/status",
    response_model=MaintenanceTaskOut,
)
def update_task_status(
    task_id: uuid.UUID,
    payload: MaintenanceTaskStatusUpdateIn,
    current_user: CurrentUser = Depends(
        require_role("technician", "supervisor", "admin")
    ),
    db: Session = Depends(get_db),
) -> MaintenanceTaskOut:
    return maintenance_service.update_task_status(
        db,
        task_id,
        payload.status,
        payload.notes,
        actor_id=current_user.id,
        actor_role=current_user.role,
    )


@router.post(
    "/tasks/{task_id}/evidence",
    response_model=TaskEvidenceOut,
    status_code=status.HTTP_201_CREATED,
)
def add_task_evidence(
    task_id: uuid.UUID,
    payload: TaskEvidenceCreateIn,
    current_user: CurrentUser = Depends(
        require_role("technician", "supervisor", "admin")
    ),
    db: Session = Depends(get_db),
) -> TaskEvidenceOut:
    return maintenance_service.add_task_evidence(
        db,
        task_id,
        payload,
        actor_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get(
    "/tasks/{task_id}/evidence",
    response_model=list[TaskEvidenceOut],
)
def list_task_evidence(
    task_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaskEvidenceOut]:
    """Any authenticated staff role can call this — the real gate is inside
    the service: technician must be on the task's team, supervisor/admin
    always see it, and anything else (e.g. a citizen) is rejected by
    _assert_can_access_task().
    """
    return maintenance_service.list_task_evidence(
        db,
        task_id,
        actor_id=current_user.id,
        actor_role=current_user.role,
    )
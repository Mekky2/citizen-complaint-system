
"""
Business logic for /api/v1/maintenance: teams, team membership, task
assignment (including rework attempts), task status updates, and task
evidence.

Enforces, in application code (per the task brief, explicitly NOT as a
database/schema change):

1. "Only users with the technician role should be added to maintenance
   teams." — see add_team_member().

2. "A technician can potentially update a maintenance task if they know the
   task ID, even if the task belongs to another maintenance team" — fixed by
   _assert_can_access_task() below, the single enforcement point every
   technician-sensitive task endpoint (status update, evidence add/list)
   calls before touching a task:

       Technician -> Maintenance Task -> Task's maintenance team
           -> is technician a member of this team?
               YES -> allow
               NO  -> 403

   Supervisor/admin are not team-scoped: they can act on any task (that is
   their operational-oversight role), so the check short-circuits for them.
   A technician with no row in maintenance_team_members for the task's
   team_id gets 403 even with a perfectly valid, correctly-formed task_id —
   that was the actual bug: the old code only checked role (technician/
   supervisor/admin), never *which* team the technician belongs to.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import TaskStatus, TicketStatus
from app.models.identity import User
from app.models.maintenance import MaintenanceTask, TaskEvidence
from app.models.org import MaintenanceTeam, MaintenanceTeamMember
from app.schemas.maintenance import (
    MaintenanceTaskCreateIn,
    MaintenanceTeamCreateIn,
    TaskEvidenceCreateIn,
)
from app.services.common import get_user_role, write_audit_log
from app.services.tickets import get_ticket, transition_ticket_status


TECHNICIAN_ROLE_NAME = "technician"
_TASK_OVERSIGHT_ROLES = ("admin", "supervisor")


def _assert_can_access_task(
    db: Session,
    task: MaintenanceTask,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> None:
    """
    The one enforcement point for "a technician can only access/update tasks
    assigned to a team they belong to". Called before ANY read or write that
    is scoped to a single, already-identified task.

    admin/supervisor: always allowed (operational oversight, never team-scoped).
    technician: allowed only if they have a maintenance_team_members row for
    task.team_id — re-checked against the database every call, never cached
    or inferred from the JWT, so losing team membership takes effect
    immediately.
    anything else: 403 (defense in depth — routers already gate on role via
    require_role, so this should be unreachable, but a function that enforces
    access must not assume its caller got that right).
    """
    if actor_role in _TASK_OVERSIGHT_ROLES:
        return

    if actor_role == TECHNICIAN_ROLE_NAME:
        is_member = db.get(
            MaintenanceTeamMember,
            (task.team_id, actor_id),
        ) is not None

        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of the maintenance team assigned to this task",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized for this task",
    )


def create_team(
    db: Session,
    payload: MaintenanceTeamCreateIn,
    *,
    actor_id: uuid.UUID,
) -> MaintenanceTeam:
    team = MaintenanceTeam(
        department_id=payload.department_id,
        name=payload.name,
    )
    db.add(team)
    db.flush()

    write_audit_log(
        db,
        actor_id=actor_id,
        action="create_maintenance_team",
        entity_type="maintenance_team",
        entity_id=team.id,
    )

    db.commit()
    db.refresh(team)
    return team


def list_teams(
    db: Session,
    *,
    department_id: uuid.UUID | None,
) -> list[MaintenanceTeam]:
    query = db.query(MaintenanceTeam)

    if department_id is not None:
        query = query.filter(
            MaintenanceTeam.department_id == department_id
        )

    return query.order_by(MaintenanceTeam.name).all()


def list_team_members(
    db: Session,
    team_id: uuid.UUID,
) -> list[dict]:
    team = db.get(MaintenanceTeam, team_id)

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance team not found",
        )

    users = (
        db.query(User)
        .join(
            MaintenanceTeamMember,
            MaintenanceTeamMember.user_id == User.id,
        )
        .filter(MaintenanceTeamMember.team_id == team_id)
        .order_by(User.name.asc())
        .all()
    )

    return [
        {
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "created_at": user.created_at,
        }
        for user in users
    ]


def add_team_member(
    db: Session,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
) -> MaintenanceTeamMember:
    team = db.get(MaintenanceTeam, team_id)

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance team not found",
        )

    role = get_user_role(db, user_id)

    if role != TECHNICIAN_ROLE_NAME:
        # The enforcement point for the task brief's explicit rule — a 403
        # application check, deliberately not a database CHECK constraint,
        # per "This should be enforced by backend business logic/RBAC, not
        # by changing the existing database schema."
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only users with the 'technician' role can be added to a maintenance team",
        )

    if db.get(MaintenanceTeamMember, (team_id, user_id)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this team",
        )

    member = MaintenanceTeamMember(
        team_id=team_id,
        user_id=user_id,
    )
    db.add(member)

    write_audit_log(
        db,
        actor_id=actor_id,
        action="add_team_member",
        entity_type="maintenance_team",
        entity_id=team_id,
        after={"user_id": str(user_id)},
    )

    db.commit()
    db.refresh(member)
    return member


def create_maintenance_task(
    db: Session,
    ticket_id: uuid.UUID,
    payload: MaintenanceTaskCreateIn,
    *,
    assigned_by: uuid.UUID,
) -> MaintenanceTask:
    """
    Creates the next attempt for a ticket: attempt_number=1 the first time,
    and attempt_number = max(existing) + 1 on the "rework" path, when a
    failed verification has sent the ticket's status back to 'assigned'.
    maintenance_tasks_ticket_attempt_unique (ticket_id, attempt_number) is the
    database's own guarantee that two attempts can never collide, even under
    a race — this function just computes the next number correctly.
    """
    ticket = get_ticket(db, ticket_id)

    if ticket.status != TicketStatus.assigned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket is '{ticket.status.value}', not 'assigned' — cannot assign a maintenance task",
        )

    team = db.get(MaintenanceTeam, payload.team_id)

    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance team not found",
        )

    next_attempt = (
        db.query(func.coalesce(func.max(MaintenanceTask.attempt_number), 0))
        .filter(MaintenanceTask.ticket_id == ticket_id)
        .scalar()
    ) + 1

    task = MaintenanceTask(
        ticket_id=ticket_id,
        team_id=payload.team_id,
        assigned_by=assigned_by,
        attempt_number=next_attempt,
        notes=payload.notes,
    )
    db.add(task)

    transition_ticket_status(
        db,
        ticket,
        to_status=TicketStatus.in_progress,
        changed_by=assigned_by,
        reason=f"Maintenance task created (attempt {next_attempt})",
    )

    write_audit_log(
        db,
        actor_id=assigned_by,
        action="create_maintenance_task",
        entity_type="ticket",
        entity_id=ticket_id,
        after={
            "team_id": str(payload.team_id),
            "attempt_number": next_attempt,
        },
    )

    db.commit()
    db.refresh(task)
    return task


def list_tasks_for_ticket(
    db: Session,
    ticket_id: uuid.UUID,
) -> list[MaintenanceTask]:
    return (
        db.query(MaintenanceTask)
        .filter(MaintenanceTask.ticket_id == ticket_id)
        .order_by(MaintenanceTask.attempt_number.desc())
        .all()
    )


def list_tasks_for_user_teams(
    db: Session,
    user_id: uuid.UUID,
) -> list[MaintenanceTask]:
    """The technician's 'My Tasks' list: every maintenance task belonging to any
    team this user is a member of, regardless of which department it is."""
    team_ids = [
        row[0]
        for row in db.query(MaintenanceTeamMember.team_id)
        .filter(MaintenanceTeamMember.user_id == user_id)
        .all()
    ]

    if not team_ids:
        return []

    return (
        db.query(MaintenanceTask)
        .filter(MaintenanceTask.team_id.in_(team_ids))
        .order_by(MaintenanceTask.assigned_at.desc())
        .all()
    )


def add_task_evidence(
    db: Session,
    task_id: uuid.UUID,
    payload: TaskEvidenceCreateIn,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> TaskEvidence:
    task = db.get(MaintenanceTask, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance task not found",
        )

    _assert_can_access_task(
        db,
        task,
        actor_id=actor_id,
        actor_role=actor_role,
    )

    evidence = TaskEvidence(
        task_id=task.id,
        type=payload.type,
        stage=payload.stage,
        url=payload.url,
    )
    db.add(evidence)

    write_audit_log(
        db,
        actor_id=actor_id,
        action="add_task_evidence",
        entity_type="maintenance_task",
        entity_id=task.id,
        after={
            "stage": payload.stage,
            "url": payload.url,
        },
    )

    db.commit()
    db.refresh(evidence)
    return evidence


def list_task_evidence(
    db: Session,
    task_id: uuid.UUID,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> list[TaskEvidence]:
    task = db.get(MaintenanceTask, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance task not found",
        )

    _assert_can_access_task(
        db,
        task,
        actor_id=actor_id,
        actor_role=actor_role,
    )

    return (
        db.query(TaskEvidence)
        .filter(TaskEvidence.task_id == task_id)
        .order_by(TaskEvidence.created_at.asc())
        .all()
    )


def update_task_status(
    db: Session,
    task_id: uuid.UUID,
    new_status: TaskStatus,
    notes: str | None,
    *,
    actor_id: uuid.UUID,
    actor_role: str,
) -> MaintenanceTask:
    task = db.get(MaintenanceTask, task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance task not found",
        )

    _assert_can_access_task(
        db,
        task,
        actor_id=actor_id,
        actor_role=actor_role,
    )

    task.status = new_status

    if notes is not None:
        task.notes = notes

    if new_status == TaskStatus.in_progress and task.started_at is None:
        task.started_at = datetime.now(timezone.utc)

    if new_status == TaskStatus.pending_verification:
        task.completed_at = datetime.now(timezone.utc)

    ticket = get_ticket(db, task.ticket_id)

    status_map = {
        TaskStatus.in_progress: TicketStatus.in_progress,
        TaskStatus.pending_verification: TicketStatus.pending_verification,
    }

    if new_status in status_map:
        transition_ticket_status(
            db,
            ticket,
            to_status=status_map[new_status],
            changed_by=actor_id,
            reason=f"Maintenance task status -> {new_status.value}",
        )

    write_audit_log(
        db,
        actor_id=actor_id,
        action="update_task_status",
        entity_type="maintenance_task",
        entity_id=task.id,
        after={"status": new_status.value},
    )

    db.commit()
    db.refresh(task)
    return task

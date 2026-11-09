"""Schemas for /api/v1/maintenance and the admin-managed teams/members."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import MediaType, TaskStatus, VerificationResult


class MaintenanceTeamCreateIn(BaseModel):
    department_id: UUID
    name: str = Field(min_length=2)


class MaintenanceTeamOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    department_id: UUID
    name: str


class MaintenanceTeamMemberAddIn(BaseModel):
    """
    user_id must belong to a user whose CURRENT role is 'technician' — enforced
    in app/services/maintenance.py, not by a database constraint (the task
    brief is explicit this is backend business logic, not a schema change).
    """

    user_id: UUID


class MaintenanceTaskCreateIn(BaseModel):
    """Assigning a ticket to a team — only reachable after supervisor approval
    (see app/services/maintenance.py, which checks ticket.status == 'assigned')."""

    team_id: UUID
    notes: str | None = None


class MaintenanceTaskOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    ticket_id: UUID
    team_id: UUID
    assigned_by: UUID
    attempt_number: int
    status: TaskStatus
    notes: str | None
    assigned_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class MaintenanceTaskStatusUpdateIn(BaseModel):
    status: TaskStatus
    notes: str | None = None


class TaskEvidenceCreateIn(BaseModel):
    type: MediaType
    stage: str = Field(default="after", pattern="^(progress|after)$")
    url: str


class TaskEvidenceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    task_id: UUID
    type: MediaType
    stage: str
    url: str
    created_at: datetime


class VerificationCreateIn(BaseModel):
    result: VerificationResult
    note: str | None = None


class VerificationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    task_id: UUID
    verifier_id: UUID
    result: VerificationResult
    note: str | None


class MaintenanceTeamMemberOut(BaseModel):
    user_id: UUID
    name: str
    email: str | None
    phone: str | None
    created_at: datetime

"""Schemas for /api/v1/supervisor."""

from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.enums import DecisionAction, Severity


class SupervisorDecisionIn(BaseModel):
    """
    The human-approval gate. action='approve' accepts the AI's recommendation
    as-is; 'edit' accepts it with overrides (category/severity/department);
    'reject' declines it entirely with a reason. Either way this is the ONLY
    way a ticket moves past awaiting_approval — see app/services/supervisor.py.
    """

    action: DecisionAction
    severity_override: Severity | None = None
    department_id_override: UUID | None = None
    category_id_override: UUID | None = None
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def require_reason_context(cls, v: str | None, info) -> str | None:
        # action is validated as part of the same model, but field order in
        # Pydantic v2 doesn't guarantee access via info.data for a later field
        # unless declared after it — action is declared first above, so it is
        # available here.
        action = info.data.get("action")
        if action == DecisionAction.reject and not v:
            raise ValueError("reason is required when rejecting an AI recommendation")
        return v


class SupervisorDecisionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    ticket_id: UUID
    recommendation_id: UUID | None
    supervisor_id: UUID
    action: DecisionAction
    changed_fields: dict | None
    reason: str | None

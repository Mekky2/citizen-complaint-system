"""
Business logic for the AI integration boundary (/api/v1/ai).

Three responsibilities, each tied to an explicit requirement from the task
brief:

1. trigger_ai_run() — backend -> AI (POST {AI_SERVICE_URL}/v1/runs via
   app/ai/client.py). Moves a ticket 'submitted' -> 'under_ai_review'. If the
   AI service is unreachable, the run is marked 'failed' with an
   error_message instead of leaving the ticket silently stuck or crashing
   the request — "AI failure handled gracefully".

2. process_ai_recommendation_callback() — AI -> backend
   (POST /api/v1/ai/recommendations). Idempotent on run_id: a run already in
   a terminal state ('succeeded'/'failed') is not reprocessed, so a retried
   webhook delivery is a safe no-op rather than a duplicate
   recommendation/ticket-transition. On success this NEVER advances the
   ticket past 'awaiting_approval' — human-in-the-loop — a supervisor
   decision (app/services/supervisor.py) is the only way past that point.

3. list_similar_case_candidates() — the read-side half of "similar-case
   retrieval should prefer completed/resolved historical tickets"; the
   write-side half is _validate_similar_case_is_historical() below, which
   rejects SIMILAR_CASE evidence that cites anything but a completed ticket.
   Together these mean a cancelled or still-active ticket can never become
   part of an AI recommendation's evidence, whether the AI service queries
   this backend for candidates first or not.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.client import AiServiceError, send_run_trigger
from app.models.ai import AiEvidence, AiRecommendation, AiRun, AiToolCall
from app.models.enums import AiEvidenceType, AiRunStatus, TicketStatus
from app.models.org import Category, Department
from app.models.ticket import Ticket
from app.schemas.ai import (
    AiEvidenceItemIn,
    AiRecommendationCallbackIn,
    AiRunTriggerLocation,
    AiRunTriggerMediaItem,
    AiRunTriggerOut,
    SimilarCaseOut,
)
from app.services.common import write_audit_log
from app.services.tickets import get_ticket, transition_ticket_status


def _resolve_category_id(db: Session, name: str | None) -> uuid.UUID | None:
    """
    STRICT by design: a category NAME that doesn't match any known category
    is a malformed/hallucinated AI response, not "no category" — so it is
    rejected with 400 rather than silently persisted as category_id=NULL
    (which would be indistinguishable from "the AI genuinely didn't
    classify this ticket", a real and valid state that `category=None`
    already represents on its own). Only a missing/empty name maps to NULL.
    """
    if not name:
        return None
    category = db.query(Category).filter(Category.name == name).first()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AI recommendation references unknown category '{name}' — rejecting rather than silently "
            "storing it as uncategorized; the AI service and this backend's category list have drifted apart",
        )
    return category.id


def _resolve_department_id(db: Session, name: str | None) -> uuid.UUID | None:
    """Same strictness as _resolve_category_id, same reason: an unrecognized
    department name is rejected, not silently dropped to NULL."""
    if not name:
        return None
    department = db.query(Department).filter(Department.name == name).first()
    if department is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AI recommendation references unknown department '{name}' — rejecting rather than silently "
            "storing it as unassigned; the AI service and this backend's department list have drifted apart",
        )
    return department.id


def _validate_similar_case_is_historical(db: Session, item: AiEvidenceItemIn) -> None:
    """
    Enforces: "Similar-case retrieval should prefer completed/resolved
    historical tickets. Do not treat cancelled or active tickets as
    authoritative historical cases." A SIMILAR_CASE item that cites anything
    other than a completed ticket is rejected with 400 before it ever reaches
    the ai_evidence table.
    """
    if item.source_type != AiEvidenceType.SIMILAR_CASE:
        return

    cited = db.get(Ticket, item.cited_ticket_id)
    if cited is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"cited_ticket_id {item.cited_ticket_id} does not exist",
        )
    if cited.status != TicketStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"cited_ticket_id {item.cited_ticket_id} has status '{cited.status.value}' — "
                "SIMILAR_CASE evidence must cite a completed ticket, never a cancelled or still-active one"
            ),
        )


def get_latest_recommendation_with_evidence(
    db: Session, ticket_id: uuid.UUID
) -> tuple[AiRecommendation, list[AiEvidence]] | None:
    """Used by the Operations Room read endpoint. AiRecommendation and AiEvidence
    have no SQLAlchemy relationship() between them (app/models/ai.py defines only
    the FK columns), so evidence is fetched with its own query rather than via
    attribute access, and the two are combined by the router into AiRecommendationOut."""
    recommendation = (
        db.query(AiRecommendation)
        .filter(AiRecommendation.ticket_id == ticket_id)
        .order_by(AiRecommendation.created_at.desc())
        .first()
    )
    if recommendation is None:
        return None
    evidence = db.query(AiEvidence).filter(AiEvidence.recommendation_id == recommendation.id).all()
    return recommendation, evidence


def list_similar_case_candidates(
    db: Session, *, category_id: uuid.UUID | None, limit: int = 20
) -> list[SimilarCaseOut]:
    """
    The historical-case pool exposed to the AI service (GET
    /api/v1/ai/similar-cases) when it builds SIMILAR_CASE evidence for a
    recommendation — restricted to completed tickets only, the read-side
    counterpart to _validate_similar_case_is_historical().

    FIX 4: returns SimilarCaseOut, NOT Ticket/TicketOut — deliberately built
    field-by-field here rather than handed to the schema via
    from_attributes, because citizen_id, address, and city must never reach
    this response at all, and the safest way to guarantee that is to never
    put them in the object being returned in the first place, rather than
    trust a response_model to strip them later.
    """
    query = db.query(Ticket).filter(Ticket.status == TicketStatus.completed)
    if category_id is not None:
        query = query.filter(Ticket.category_id == category_id)
    tickets = query.order_by(Ticket.updated_at.desc()).limit(limit).all()

    return [
        SimilarCaseOut(
            ticket_id=t.id,
            category_id=t.category_id,
            description=t.description,
            severity=t.severity,
            status=t.status,
            governorate=t.governorate,
            created_at=t.created_at,
            completed_at=t.updated_at,
        )
        for t in tickets
    ]


async def trigger_ai_run(db: Session, ticket_id: uuid.UUID, *, actor_id: uuid.UUID) -> AiRun:
    ticket = get_ticket(db, ticket_id, with_details=True)
    if ticket.status != TicketStatus.submitted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket is '{ticket.status.value}', not 'submitted' — cannot trigger AI review",
        )

    run = AiRun(ticket_id=ticket.id, status=AiRunStatus.pending)
    db.add(run)
    transition_ticket_status(
        db, ticket, to_status=TicketStatus.under_ai_review, changed_by=actor_id, reason="AI run triggered",
    )
    write_audit_log(db, actor_id=actor_id, action="trigger_ai_run", entity_type="ticket", entity_id=ticket.id)
    db.commit()
    db.refresh(run)

    trigger_payload = AiRunTriggerOut(
        ticket_id=ticket.id,
        description=ticket.description,
        category_hint=str(ticket.category_id) if ticket.category_id else None,
        media=[AiRunTriggerMediaItem(type=m.type.value, url=m.url) for m in ticket.media],
        location=AiRunTriggerLocation(lat=ticket.lat, lng=ticket.lng, governorate=ticket.governorate),
    )

    try:
        await send_run_trigger(run_id=run.id, payload=trigger_payload)
    except AiServiceError as exc:
        # The AI service being unreachable must not corrupt ticket state —
        # record the failure on the run itself and leave the ticket visibly
        # in 'under_ai_review' rather than silently reverting it, so a
        # supervisor can see a run is stuck and retrigger or intervene.
        run.status = AiRunStatus.failed
        run.error_message = str(exc)[:2000]
        db.commit()
        db.refresh(run)

    return run


def process_ai_recommendation_callback(db: Session, payload: AiRecommendationCallbackIn) -> AiRun:
    run = db.get(AiRun, payload.run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown run_id")
    if run.ticket_id != payload.ticket_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ticket_id does not match the ticket this run was triggered for",
        )

    # Idempotency key: run_id. A run already in a terminal state is not
    # reprocessed — a retried webhook delivery is a safe no-op.
    if run.status in (AiRunStatus.succeeded, AiRunStatus.failed):
        return run

    run.completed_at = datetime.now(timezone.utc)
    if payload.model:
        run.model_provider = payload.model.provider
        run.model_name = payload.model.name

    if payload.status == "failed":
        run.status = AiRunStatus.failed
        run.error_message = payload.error_message
        ticket = get_ticket(db, run.ticket_id)
        transition_ticket_status(
            db, ticket, to_status=TicketStatus.submitted, changed_by=None,
            reason=f"AI run failed: {payload.error_message}",
        )
        db.commit()
        db.refresh(run)
        return run

    rec_payload = payload.recommendation  # guaranteed non-None by the schema's model_validator

    # Resolved — and therefore validated — BEFORE run.status is touched: if
    # either name is unrecognized, this raises 400 here and run.status stays
    # whatever it already was (still 'pending'), not silently flipped to
    # 'succeeded' on a recommendation that referenced garbage. See
    # _resolve_category_id/_resolve_department_id docstrings for why an
    # unknown name is a hard error rather than an implicit NULL.
    category_id = _resolve_category_id(db, rec_payload.category)
    department_id = _resolve_department_id(db, rec_payload.department)

    run.status = AiRunStatus.succeeded

    recommendation = AiRecommendation(
        ai_run_id=run.id,
        ticket_id=run.ticket_id,
        category_id=category_id,
        severity=rec_payload.severity,
        department_id=department_id,
        confidence=rec_payload.confidence,
        explanation=rec_payload.explanation,
        factors=rec_payload.factors or None,
    )
    db.add(recommendation)
    db.flush()  # assigns recommendation.id for the evidence rows below

    for item in payload.evidence:
        _validate_similar_case_is_historical(db, item)
        db.add(
            AiEvidence(
                recommendation_id=recommendation.id,
                evidence_type=item.source_type,
                knowledge_chunk_id=item.knowledge_chunk_id,
                cited_ticket_id=item.cited_ticket_id,
                snippet=item.snippet,
                similarity_score=item.similarity_score,
            )
        )

    for tool_call in payload.tool_calls:
        db.add(
            AiToolCall(
                ai_run_id=run.id,
                tool_name=tool_call.tool_name,
                input=tool_call.input,
                output=tool_call.output,
                status=tool_call.status,
                duration_ms=tool_call.duration_ms,
            )
        )

    ticket = get_ticket(db, run.ticket_id)
    transition_ticket_status(
        db, ticket, to_status=TicketStatus.awaiting_approval, changed_by=None,
        reason="AI recommendation received — awaiting supervisor decision",
    )

    db.commit()
    db.refresh(run)
    return run

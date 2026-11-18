"""Public API routes for the two agents.

``POST /api/v1/chat`` is the single entry point used by the frontend:

* complaint intent (or an active complaint session) -> conversational Complaint Agent;
* question / greeting / emergency intent           -> RAG Agent (Arabic answer + sources).

Both paths are human-in-the-loop: a ticket is only created after the citizen confirms, and it
starts as ``Pending``.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.complaint_agent.conversation import handle_message, looks_like_complaint
from app.services.runtime import get_runtime
from app.services.ticket_store import InvalidStatusTransition, to_public_dict

router = APIRouter(prefix="/api/v1", tags=["agents"])

ACTIVE_COMPLAINT_STAGES = {"collecting", "awaiting_confirmation"}
TicketStatus = Literal[
    "Declined",
    "Pending",
    "Approved",
    "Dismissed",
    "In Progress",
    "Verifying",
    "Done",
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="demo-session", min_length=1, max_length=100)
    user_id: str | None = Field(default=None, max_length=100)


class SourceOut(BaseModel):
    title: str
    excerpt: str
    page: int | None = None


class ChatResponse(BaseModel):
    type: Literal["complaint", "rag"]
    session_id: str
    reply_ar: str
    stage: str | None = None
    ticket: dict[str, Any] | None = None
    missing_fields: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    handoff_to: str | None = None
    sources: list[SourceOut] = Field(default_factory=list)
    confidence: str | None = None
    found_in_kb: bool | None = None
    review_notes: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    status: TicketStatus
    reviewer_note: str | None = Field(default=None, max_length=500)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    runtime = get_runtime()
    session = runtime.session(request.session_id)
    rag = runtime.rag_agent()

    if session.stage in ACTIVE_COMPLAINT_STAGES:
        return _complaint_turn(request, session, rag)

    intent = rag.detect_intent(request.message)
    if intent in {"complaint"} or looks_like_complaint(request.message):
        return _complaint_turn(request, session, rag)

    return _rag_turn(request, rag)


def _complaint_turn(request: ChatRequest, session, rag) -> ChatResponse:
    runtime = get_runtime()
    result = handle_message(
        session,
        request.message,
        llm=runtime.llm,
        store=runtime.ticket_store,
        emergency_numbers=runtime.emergency_numbers,
    )

    # The complaint agent hands questions/procedures to the RAG agent.
    if result.get("handoff_to") == "rag":
        rag_result = rag.run(
            {
                "query": request.message,
                "ticket_id": f"SESSION-{request.session_id}",
                "session_id": request.session_id,
                "conversation_history": [],
                "tool_calls": 0,
            }
        )
        return ChatResponse(
            type="rag",
            session_id=request.session_id,
            reply_ar=rag_result["answer"],
            stage=session.stage,
            handoff_to="rag",
            sources=[SourceOut(**source.model_dump()) for source in rag_result["sources"]],
            confidence=rag_result["confidence"],
            found_in_kb=rag_result["found_in_kb"],
            review_notes=rag_result["review_notes"],
        )

    return ChatResponse(
        type="complaint",
        session_id=request.session_id,
        reply_ar=result["reply_ar"],
        stage=result["stage"],
        ticket=result.get("ticket"),
        missing_fields=result.get("missing_fields", []),
        requires_confirmation=result.get("requires_confirmation", False),
        handoff_to=result.get("handoff_to"),
        review_notes=result.get("review_notes", []),
    )


def _rag_turn(request: ChatRequest, rag) -> ChatResponse:
    result = rag.run(
        {
            "query": request.message,
            "ticket_id": f"SESSION-{request.session_id}",
            "session_id": request.session_id,
            "conversation_history": [],
            "tool_calls": 0,
        }
    )
    return ChatResponse(
        type="rag",
        session_id=request.session_id,
        reply_ar=result["answer"],
        sources=[SourceOut(**source.model_dump()) for source in result["sources"]],
        confidence=result["confidence"],
        found_in_kb=result["found_in_kb"],
        review_notes=result["review_notes"],
    )


@router.get("/tickets")
def list_tickets() -> list[dict[str, Any]]:
    return [to_public_dict(ticket) for ticket in get_runtime().ticket_store.list()]


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict[str, Any]:
    ticket = get_runtime().ticket_store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return to_public_dict(ticket)


@router.post("/tickets/{ticket_id}/review")
def review_ticket(ticket_id: str, request: ReviewRequest) -> dict[str, Any]:
    store = get_runtime().ticket_store
    ticket = store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        updated = store.update_status(ticket_id, request.status)
    except InvalidStatusTransition as exc:
        raise HTTPException(
            status_code=409,
            detail=f"انتقال حالة غير مسموح به: {exc}",
        ) from exc
    if request.reviewer_note and updated:
        updated = store.add_note(ticket_id, f"REVIEWER:{request.reviewer_note}")
    return to_public_dict(updated)


@router.get("/knowledge/status")
def knowledge_status() -> dict[str, Any]:
    runtime = get_runtime()
    return {
        "documents": len(runtime.knowledge_base.documents),
        "chunks": runtime.knowledge_base.chunk_count,
        "embedding_provider": runtime.settings.embedding_provider,
        "embedding_dimension": runtime.settings.embedding_dimension,
        "ingest": runtime.knowledge_stats,
    }

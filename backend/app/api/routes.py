"""Public API routes for the agents.

``POST /api/v1/chat`` is the single entry point used by the frontend:

* complaint intent (or an active complaint session) -> conversational Complaint Agent;
* question / greeting / emergency intent           -> RAG Agent (Arabic answer + sources).

Both paths are human-in-the-loop: a ticket is only created after the citizen confirms, and it
starts as ``Pending``.

Load protection: a per-client sliding window returns ``429`` and a bounded in-flight gate
returns ``503``, both with ``Retry-After`` and an Arabic message. Neither can produce a 500.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.services.observability import log_request, reset_trace, start_trace
from app.services.runtime import get_runtime
from app.services.ticket_store import InvalidStatusTransition, to_public_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["agents"])

TicketStatus = Literal[
    "Declined",
    "Pending",
    "Approved",
    "Dismissed",
    "In Progress",
    "Verifying",
    "Done",
]

BUSY_RATE_LIMIT = "عدد الطلبات كبير حاليًا. يُرجى المحاولة بعد قليل."
BUSY_OVERLOAD = "الخدمة مشغولة حاليًا. يُرجى المحاولة بعد لحظات."
INTERNAL_FALLBACK = "تعذّر إكمال الطلب الآن. يُرجى المحاولة مرة أخرى بعد قليل."


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
    # True when the answer came from the offline fallback (all providers down/busy/over budget).
    degraded: bool = False
    request_id: str | None = None


class ReviewRequest(BaseModel):
    status: TicketStatus
    reviewer_note: str | None = Field(default=None, max_length=500)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request, response: Response) -> ChatResponse:
    runtime = get_runtime()

    client_id = request.user_id or _client_id(http_request)
    allowed, retry_after = runtime.rate_limiter.allow(client_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=BUSY_RATE_LIMIT,
            headers={"Retry-After": str(int(max(1, retry_after)))},
        )

    acquired = await asyncio.to_thread(
        runtime.request_gate.acquire, runtime.settings.api_queue_timeout_seconds
    )
    if not acquired:
        raise HTTPException(
            status_code=503,
            detail=BUSY_OVERLOAD,
            headers={"Retry-After": "2"},
        )

    trace = start_trace()
    try:
        result = await asyncio.to_thread(
            runtime.chat, request.message, request.session_id, request.user_id
        )
    except Exception:  # noqa: BLE001 - a request must never surface a 500/stack trace
        logger.error("chat failed type=%s request_id=%s", "UnhandledError", trace.request_id)
        raise HTTPException(status_code=503, detail=INTERNAL_FALLBACK) from None
    finally:
        runtime.request_gate.release()

    log_request(
        trace,
        path="/api/v1/chat",
        type=result.get("type"),
        stage=result.get("stage"),
    )
    response.headers["X-Request-ID"] = trace.request_id
    reset_trace()
    return ChatResponse(**result)


def _client_id(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.get("/tickets")
async def list_tickets() -> list[dict[str, Any]]:
    return [to_public_dict(ticket) for ticket in get_runtime().ticket_store.list()]


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str) -> dict[str, Any]:
    ticket = get_runtime().ticket_store.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return to_public_dict(ticket)


@router.post("/tickets/{ticket_id}/review")
async def review_ticket(ticket_id: str, request: ReviewRequest) -> dict[str, Any]:
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
async def knowledge_status() -> dict[str, Any]:
    runtime = get_runtime()
    return {
        "documents": len(runtime.knowledge_base.documents),
        "chunks": runtime.knowledge_base.chunk_count,
        "embedding_provider": runtime.settings.embedding_provider,
        "embedding_dimension": runtime.settings.embedding_dimension,
        "version": runtime.knowledge_base.version,
        "ingest": runtime.knowledge_stats,
    }


@router.get("/admin/status")
async def admin_status() -> dict[str, Any]:
    """Provider/key counts and load counters. Never contains keys or complaint text."""
    return get_runtime().admin_status()

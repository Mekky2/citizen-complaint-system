"""
Thin HTTP client for the one outbound call this backend makes to the AI
service: POST {AI_SERVICE_URL}/v1/runs to trigger a run.

Request/response SHAPES live in app/schemas/ai.py, not duplicated here —
app/ai/ is deliberately just the transport (client + its own exception), so
there is exactly one definition of the AI contract's shape in the codebase.
This is a conscious departure from the task brief's suggested
`app/ai/schemas.py`: a second schema file would either duplicate
app/schemas/ai.py or re-export it, and neither reduces risk of the two
drifting apart — one file is strictly safer.

The AI service calls BACK into this backend to deliver results
(POST /api/v1/ai/recommendations, handled by app/services/ai.py) — a
recommendation is never the return value of send_run_trigger() — because an
AI run (model calls, RAG lookups, tool use) can run far longer than it is
reasonable to hold a citizen-facing HTTP request open.

ASYNC: this is the one piece of genuine I/O-bound outbound networking in the
whole backend (everything else is synchronous SQLAlchemy against Postgres),
so it is the one function worth making a real `async def` with
`httpx.AsyncClient` rather than the blocking `httpx.post()` this module used
to call. The call site (app/services/ai.py:trigger_ai_run, and the router
above it) is async all the way up specifically so this `await` is a real
await, not a sync call wrapped and forgotten inside an async def — that
mismatch (blocking I/O inside an `async def`, stalling the whole event loop
for every other in-flight request) is the exact anti-pattern this change
avoids. Every other router in this codebase stays a plain sync `def`, which
is the correct FastAPI pattern for handlers that only do blocking DB I/O —
FastAPI already runs those in a worker thread pool, so there is nothing to
convert there.
"""

import uuid

import httpx

from app.config import get_settings
from app.schemas.ai import AiRunTriggerOut

settings = get_settings()


class AiServiceError(Exception):
    """Raised when the AI service cannot be reached, times out, or rejects the trigger request."""


async def send_run_trigger(*, run_id: uuid.UUID, payload: AiRunTriggerOut) -> None:
    url = f"{settings.ai_service_url.rstrip('/')}/v1/runs"
    headers = {"X-AI-Service-Secret": settings.ai_service_shared_secret}
    body = payload.model_dump(mode="json")
    body["run_id"] = str(run_id)

    try:
        async with httpx.AsyncClient(timeout=settings.ai_service_timeout_seconds) as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AiServiceError(f"AI service request failed: {exc}") from exc

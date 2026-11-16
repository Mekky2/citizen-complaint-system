"""Complaint Agent entry point.

    run_complaint_agent(state, llm, rag) -> dict      (never raises)

Pipeline (5 tool calls on the happy path; docs/system_architecture.md says 4, the extra one
is the grounding verification, so the Orchestrator owner should update that number):
    1. categorize          (LLM)
    2. classify_severity   (LLM)
    3. RAG retrieve        (teammate's component)
    4. generate_recommendations (LLM, uses only step 3's sources)
    5. verify_support      (LLM, checks each recommendation against its cited source)
Steps 4-5 are skipped when RAG returns nothing; step 5 is skipped when nothing survives step 4.

Global limits (timeouts, retries, loop guard, circuit breaker, 8-call cap enforcement,
PII masking in logs) belong to the Orchestrator. The agent only keeps the `tool_calls`
counter in step with the calls it makes and stops if the incoming limit is reached.
"""

import logging
from typing import Any

from pydantic import ValidationError

from app.agents.complaint_agent import rules, tools
from app.agents.complaint_agent.interfaces import LLMClient, RagRetriever
from app.agents.complaint_agent.schemas import (
    CATEGORIES,
    AgentFailure,
    AgentInput,
    AgentSuccess,
    FailureReason,
    RagChunk,
)

# Log only ticket id and failure code. Never log description, name or national id.
logger = logging.getLogger(__name__)

TOP_K = 5


class _Run:
    """Holds the counter and the partial results so a failure can still report them."""

    def __init__(self, inp: AgentInput):
        self.inp = inp
        self.tool_calls = inp.tool_calls
        self.category: str | None = None
        self.severity: str | None = None

    def count_call(self) -> None:
        if self.tool_calls >= self.inp.tool_call_limit:
            raise tools.ToolError(FailureReason.TOOL_CALL_LIMIT_EXCEEDED)
        self.tool_calls += 1

    def failure(self, reason: FailureReason) -> dict[str, Any]:
        logger.warning("complaint_agent failed ticket=%s reason=%s", self.inp.ticket_id, reason)
        return AgentFailure(
            ticket_id=self.inp.ticket_id,
            failure_reason=reason,
            category=self.category,
            severity=self.severity,
            recommendations=[],
            tool_calls=self.tool_calls,
        ).model_dump(mode="json")


def _failure_without_input(state: Any, reason: FailureReason) -> dict[str, Any]:
    """Failure for input so broken that AgentInput could not even be built."""
    ticket_id, calls = "UNKNOWN", 0
    if isinstance(state, dict):
        ticket_id = str(state.get("ticket_id") or "UNKNOWN")
        calls = state["tool_calls"] if isinstance(state.get("tool_calls"), int) else 0
    return AgentFailure(ticket_id=ticket_id, failure_reason=reason, tool_calls=calls).model_dump(
        mode="json"
    )


def _retrieve(run: _Run, rag: RagRetriever, description: str, category: str) -> list[RagChunk]:
    run.count_call()
    try:
        raw = rag.retrieve(description, category, TOP_K)
        return [RagChunk.model_validate(c) for c in raw]
    except Exception as exc:  # RAG outage or malformed items from the retriever
        raise tools.ToolError(FailureReason.RAG_UNAVAILABLE) from exc


def run_complaint_agent(state: dict[str, Any], llm: LLMClient, rag: RagRetriever) -> dict[str, Any]:
    try:
        inp = AgentInput.model_validate(state)
    except ValidationError:
        return _failure_without_input(state, FailureReason.INVALID_INPUT)

    run = _Run(inp)
    description = inp.payload.get("description")
    authority = inp.payload.get("authority")
    if not isinstance(description, str) or not description.strip() or authority not in CATEGORIES:
        return run.failure(FailureReason.INVALID_INPUT)

    # Only the description (and authority as a hint) is sent to the LLM and RAG:
    # no citizen name, national id, location or attachments.
    notes: list[str] = []
    try:
        run.count_call()
        run.category, unclear = tools.categorize(llm, description, authority)
        if unclear:
            notes.append(
                "AMBIGUOUS_DESCRIPTION: category could not be determined from the text; "
                "the citizen's selected authority was used."
            )
        elif run.category != authority:
            notes.append(
                f"CATEGORY_DIFFERS_FROM_AUTHORITY: classified as {run.category} "
                f"but the citizen selected {authority}."
            )

        run.count_call()
        sev = tools.classify_severity(llm, description, run.category)
        run.severity = sev.severity
        notes.extend(rules.severity_review_notes(description, sev.severity, sev.confidence))

        chunks = _retrieve(run, rag, description, run.category)

        recommendations: list[str] = []
        if not chunks:  # no evidence -> no LLM call, no recommendations
            notes.append(
                "NO_RETRIEVED_EVIDENCE: the knowledge base returned nothing; "
                "no recommendations were generated."
            )
        else:
            run.count_call()
            drafts, dropped = tools.generate_recommendations(
                llm, description, run.category, run.severity, chunks
            )
            if drafts:
                run.count_call()  # fail closed: if the limit is hit here the ticket fails
                supported = tools.verify_support(llm, description, drafts, chunks)
                dropped += len(drafts) - len(supported)
                drafts = supported
            recommendations = [tools.render_recommendation(d, chunks) for d in drafts]
            if dropped:
                notes.append(
                    f"RECOMMENDATIONS_REMOVED: {dropped} draft(s) removed because the retrieved "
                    "sources did not support them."
                )
            if not recommendations:
                notes.append(
                    "NO_SUPPORTED_RECOMMENDATIONS: retrieved evidence was insufficient or "
                    "irrelevant, so no recommendation is given."
                )
    except tools.ToolError as err:
        return run.failure(err.reason)
    except Exception:  # last resort: the agent must return a Failed payload, not raise
        logger.exception("complaint_agent unexpected error ticket=%s", inp.ticket_id)
        return run.failure(FailureReason.INTERNAL_ERROR)

    return AgentSuccess(
        ticket_id=inp.ticket_id,
        payload=inp.payload,  # returned exactly as received
        category=run.category,
        severity=run.severity,
        recommendations=recommendations,
        rag_context=chunks,
        tool_calls=run.tool_calls,
        review_notes=notes,
    ).model_dump(mode="json")

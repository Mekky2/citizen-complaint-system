"""Pydantic models for the Complaint Agent.

Field names follow docs/system_architecture.md ("Agent State & Payload Specifications").
Agent status (Processing/Completed/Failed) is NOT the ticket lifecycle status.
"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Taxonomy ---------------------------------------------------------------
# ASSUMPTION: docs list "Water, Electricity, Roads, Garbage" as examples, while the
# Orchestrator's VALID_AUTHORITIES is Water, Electricity, Roads, Environment. We follow
# the code (it is what actually validates tickets); "Garbage" complaints map to
# "Environment". Change ONLY this tuple if the team settles on another taxonomy.
CATEGORIES: tuple[str, ...] = ("Water", "Electricity", "Roads", "Environment")

# Severity levels from the docs. "Unclassified" is set by the Orchestrator on failure,
# never by this agent.
SEVERITIES: tuple[str, ...] = ("Critical", "Medium", "Weak")


class AgentStatus(StrEnum):
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class FailureReason(StrEnum):
    # Documented in system_architecture.md:
    TOOL_CALL_LIMIT_EXCEEDED = "TOOL_CALL_LIMIT_EXCEEDED"
    # PROPOSED by the Complaint Agent (not yet in the docs; Orchestrator owner must accept):
    INVALID_INPUT = "INVALID_INPUT"
    LLM_PROVIDER_ERROR = "LLM_PROVIDER_ERROR"
    MALFORMED_LLM_RESPONSE = "MALFORMED_LLM_RESPONSE"
    RAG_UNAVAILABLE = "RAG_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# --- Input ------------------------------------------------------------------
class AgentInput(BaseModel):
    """Orchestrator -> Complaint Agent. Payload is kept as the original dict so it can be
    returned untouched; only the fields the agent needs are checked."""

    model_config = ConfigDict(extra="ignore")

    ticket_id: str = Field(min_length=1)
    status: str = "Processing"
    payload: dict[str, Any]
    severity: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    tool_calls: int = Field(default=0, ge=0)
    tool_call_limit: int = Field(default=8, ge=1)


class RagChunk(BaseModel):
    """One retrieved passage. This is also the `rag_context` item in the output."""

    source: str = Field(min_length=1)  # e.g. "Regulation W-12"
    excerpt: str = Field(min_length=1)


# --- Output -----------------------------------------------------------------
class AgentSuccess(BaseModel):
    ticket_id: str
    status: Literal["Completed"] = "Completed"
    payload: dict[str, Any]
    category: str
    severity: str
    recommendations: list[str]
    rag_context: list[RagChunk]
    tool_calls: int
    # EXTENSION beyond the documented contract (needs team approval): reasons a human should
    # look closer, as "CODE: explanation" strings. Empty list when there is nothing to flag.
    review_notes: list[str] = Field(default_factory=list)


class AgentFailure(BaseModel):
    ticket_id: str
    status: Literal["Failed"] = "Failed"
    failure_reason: FailureReason
    category: str | None = None
    severity: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    tool_calls: int = 0


# --- Validated LLM answers (internal) ---------------------------------------
class CategoryAnswer(BaseModel):
    category: str  # a taxonomy value, or "Unclear"


class SeverityAnswer(BaseModel):
    severity: Literal["Critical", "Medium", "Weak"]
    confidence: Literal["high", "low"] = "low"  # a missing value is treated as not confident


class RecommendationDraft(BaseModel):
    text: str = Field(min_length=1)
    source_ids: list[int] = Field(min_length=1)  # 1-based indexes into the retrieved chunks


class RecommendationAnswer(BaseModel):
    recommendations: list[RecommendationDraft]


class Verdict(BaseModel):
    index: int
    supported: bool


class VerificationAnswer(BaseModel):
    verdicts: list[Verdict]

"""
Schemas for the AI integration boundary (/api/v1/ai) and for app/ai/client.py.

Two directions, two schemas, matching the contract in the task brief:

  Backend -> AI:  POST {AI_SERVICE_URL}/v1/runs        -> AiRunTriggerOut (what we send)
  AI -> Backend:  POST /api/v1/ai/recommendations       -> AiRecommendationCallbackIn (what we accept)

AiRecommendationCallbackIn is the actual safety boundary for "no chain-of-thought
storage": explanation/factors are length- and shape-constrained here, BEFORE
anything reaches the database, and the schema has no field that could hold a
raw reasoning trace even if the AI service sent one — an extra field is
silently dropped by Pydantic's default config, not persisted.
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import AiEvidenceType, LegalSourceType, Severity, TicketStatus

# A chain-of-thought dump is usually thousands of characters; a genuine
# structured explanation ("why this category/severity") is a sentence or two.
# This cap is a deliberate backstop, not a stylistic preference.
MAX_EXPLANATION_LENGTH = 1000
MAX_FACTOR_LENGTH = 200
MAX_FACTORS = 10


# --- Backend -> AI --------------------------------------------------------

class AiRunTriggerMediaItem(BaseModel):
    type: Literal["image", "video", "audio"]
    url: str


class AiRunTriggerLocation(BaseModel):
    lat: float
    lng: float
    governorate: str | None = None


class AiRunTriggerOut(BaseModel):
    """Body the backend POSTs to {AI_SERVICE_URL}/v1/runs to trigger a run."""

    ticket_id: uuid.UUID
    description: str
    category_hint: str | None = None
    media: list[AiRunTriggerMediaItem] = []
    location: AiRunTriggerLocation


# --- AI -> Backend ---------------------------------------------------------

class AiRecommendationPayload(BaseModel):
    category: str | None = None
    severity: Severity | None = None
    department: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    explanation: str | None = Field(default=None, max_length=MAX_EXPLANATION_LENGTH)
    factors: list[str] = Field(default_factory=list)

    @field_validator("factors")
    @classmethod
    def validate_factors(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_FACTORS:
            raise ValueError(f"factors cannot have more than {MAX_FACTORS} items")
        for factor in v:
            if len(factor) > MAX_FACTOR_LENGTH:
                raise ValueError(
                    f"each factor must be at most {MAX_FACTOR_LENGTH} characters "
                    "(this is a short structured list, not free-form reasoning)"
                )
        return v


class AiEvidenceItemIn(BaseModel):
    """
    One piece of evidence. source_type decides which reference field is
    required — mirrors the database's ai_evidence_type_source_check CHECK
    constraint exactly, so a malformed payload is rejected here, in a clear
    400, rather than failing an opaque database constraint later.
    """

    source_type: AiEvidenceType
    knowledge_chunk_id: uuid.UUID | None = None
    cited_ticket_id: uuid.UUID | None = None
    snippet: str | None = Field(default=None, max_length=1000)
    similarity_score: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_reference_matches_type(self) -> "AiEvidenceItemIn":
        if self.source_type == AiEvidenceType.LEGAL_EVIDENCE:
            if self.knowledge_chunk_id is None or self.cited_ticket_id is not None:
                raise ValueError(
                    "LEGAL_EVIDENCE must set knowledge_chunk_id and must NOT set cited_ticket_id"
                )
        else:  # SIMILAR_CASE
            if self.cited_ticket_id is None or self.knowledge_chunk_id is not None:
                raise ValueError(
                    "SIMILAR_CASE must set cited_ticket_id and must NOT set knowledge_chunk_id "
                    "(a previous ticket must never be sent as legal evidence)"
                )
        return self


class AiToolCallIn(BaseModel):
    """Structured tool call record only — there is deliberately no field here that
    could hold a raw reasoning/thinking trace."""

    tool_name: str
    input: dict
    output: dict | None = None
    status: str | None = None
    duration_ms: int | None = None


class AiModelInfo(BaseModel):
    provider: str | None = None
    name: str | None = None


class AiRecommendationCallbackIn(BaseModel):
    """Body the AI service POSTs to /api/v1/ai/recommendations."""

    run_id: uuid.UUID  # the ai_runs.id this callback reports on — idempotency key
    ticket_id: uuid.UUID
    status: Literal["succeeded", "failed"]
    model: AiModelInfo | None = None
    error_message: str | None = Field(default=None, max_length=2000)
    recommendation: AiRecommendationPayload | None = None
    evidence: list[AiEvidenceItemIn] = []
    tool_calls: list[AiToolCallIn] = []

    @model_validator(mode="after")
    def validate_status_consistency(self) -> "AiRecommendationCallbackIn":
        if self.status == "succeeded" and self.recommendation is None:
            raise ValueError("status=succeeded requires a recommendation")
        if self.status == "failed" and not self.error_message:
            raise ValueError("status=failed requires error_message")
        return self


# --- Read models (what the Operations Room reads back) --------------------

class AiEvidenceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    evidence_type: AiEvidenceType
    knowledge_chunk_id: uuid.UUID | None
    cited_ticket_id: uuid.UUID | None
    snippet: str | None
    similarity_score: float | None


class AiRecommendationOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    ai_run_id: uuid.UUID
    ticket_id: uuid.UUID
    category_id: uuid.UUID | None
    severity: Severity | None
    department_id: uuid.UUID | None
    confidence: float | None
    explanation: str | None
    factors: list | None
    evidence: list[AiEvidenceOut] = []


class AiRunOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    ticket_id: uuid.UUID
    status: str
    model_provider: str | None
    model_name: str | None
    error_message: str | None


# --- Legal RAG boundary (FIX 3: POST /api/v1/ai/legal-search) -------------

class LegalSearchIn(BaseModel):
    """
    The AI service sends an already-computed query embedding — this backend
    does not run an embedding model itself, it only does the pgvector
    similarity search. query_embedding has no fixed length requirement here
    (no Field(min_length=1536) or similar): legal_knowledge_chunks.embedding
    is an unconstrained vector column, and app/services/legal_rag.py matches
    this query against chunks whose OWN embedding_dim equals
    len(query_embedding), whatever that is.
    """

    query_embedding: list[float] = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)
    source_type: LegalSourceType | None = None
    department_id: uuid.UUID | None = None


class LegalSearchResultOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    title: str
    source_type: LegalSourceType
    reference_number: str | None
    department_id: uuid.UUID | None
    similarity_score: float


# --- Similar Cases boundary (FIX 4: GET /api/v1/ai/similar-cases) ---------

class SimilarCaseOut(BaseModel):
    """
    The AI service's view of a historical ticket — deliberately NOT TicketOut.
    No citizen_id, no phone/email (TicketOut doesn't even carry those, but
    nothing here does either), no address, no city: just enough to judge
    similarity and to be cited as SIMILAR_CASE evidence. governorate is kept
    as coarse location context; the ticket's exact street address is not.

    completed_at is Ticket.updated_at at read time: the schema has no
    dedicated "completed_at" column, and every row returned here is already
    filtered to status == 'completed' (see
    app/services/ai.py:list_similar_case_candidates), so updated_at IS the
    moment it became completed, to the precision the data actually supports.
    """

    model_config = {"from_attributes": True}

    ticket_id: uuid.UUID
    category_id: uuid.UUID | None
    description: str
    severity: Severity | None
    status: TicketStatus
    governorate: str | None
    created_at: datetime
    completed_at: datetime

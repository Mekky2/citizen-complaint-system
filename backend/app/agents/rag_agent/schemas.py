"""Pydantic models for the RAG Agent."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnswerSource(BaseModel):
    """One source that an answer cites."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, description="Document title")
    excerpt: str = Field(min_length=1, description="Relevant excerpt from the document")
    page: int | None = Field(default=None, description="Page number, if available")


class ChatTurn(BaseModel):
    """One turn in a conversation."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(min_length=1, description="User or assistant message")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata like timestamp, etc."
    )


class RAGAgentState(BaseModel):
    """State for the RAG agent conversation."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str = Field(min_length=1)
    user_id: str | None = Field(default=None, description="Citizen ID if authenticated")
    conversation_history: list[ChatTurn] = Field(
        default_factory=list,
        description="Previous turns in the conversation",
    )
    tool_calls: int = Field(default=0, ge=0, description="Number of LLM calls made")


class RAGAgentInput(BaseModel):
    """Orchestrator -> RAG Agent input."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str = Field(min_length=1)
    query: str = Field(min_length=1, description="User's question or inquiry")
    authority: str | None = Field(
        default=None,
        description="Authority/department, if known from context",
    )
    conversation_history: list[ChatTurn] | None = Field(
        default=None,
        description="Previous turns in the conversation",
    )
    user_id: str | None = Field(default=None, description="Citizen ID if authenticated")
    tool_calls: int = Field(default=0, ge=0, description="Number of LLM calls made so far")
    tool_call_limit: int = Field(default=4, ge=1, description="Maximum tool calls allowed")
    session_id: str = Field(min_length=1, description="Unique session identifier for the user")


class RAGAgentOutput(BaseModel):
    """RAG Agent -> Orchestrator output."""

    model_config = ConfigDict(frozen=True)

    ticket_id: str = Field(min_length=1)
    status: str = Field(description="'completed' or 'handoff'")
    handoff_to: str | None = Field(default=None, description="'rag' for non-complaint questions")
    answer: str = Field(min_length=1, description="Answer in Arabic")
    sources: list[AnswerSource] = Field(default_factory=list, description="Cited sources")
    confidence: str = Field(description="'high', 'medium', 'low' based on similarity")
    found_in_kb: bool = Field(description="Whether answer was generated from KB (vs. fallback)")
    tool_calls: int = Field(ge=0, description="Number of LLM/tool calls made")
    review_notes: list[str] = Field(
        default_factory=list,
        description="Notes like 'LOW_SIMILARITY', 'OUT_OF_SCOPE'",
    )


class SearchQuery(BaseModel):
    """Normalized search query."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1)
    normalized_query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=10)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class RetrievalResult(BaseModel):
    """Result of a retrieval operation."""

    model_config = ConfigDict(frozen=True)

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    page: int | None = Field(default=None)
    similarity: float = Field(ge=0.0, le=1.0)

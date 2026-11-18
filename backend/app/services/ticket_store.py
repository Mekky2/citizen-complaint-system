"""Ticket persistence for the complaint flow.

This is a small in-memory implementation with the same shape a Supabase-backed repository
would have. It exists so the conversational agent and the API can be tested end-to-end
without a database. The status always starts as ``Pending``: a human reviewer makes the final
decision (human-in-the-loop requirement). Status names and transitions follow
``docs/system_architecture.md`` exactly.

Never store or log national IDs or phone numbers here; the agent deliberately does not
collect them.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge_base.keywords import tokenize_for_search

# Ticket lifecycle statuses (docs/system_architecture.md).
STATUS_DECLINED = "Declined"
STATUS_PENDING = "Pending"
STATUS_APPROVED = "Approved"
STATUS_DISMISSED = "Dismissed"
STATUS_IN_PROGRESS = "In Progress"
STATUS_VERIFYING = "Verifying"
STATUS_DONE = "Done"

TICKET_STATUSES = (
    STATUS_DECLINED,
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_DISMISSED,
    STATUS_IN_PROGRESS,
    STATUS_VERIFYING,
    STATUS_DONE,
)

# Tickets that can still be duplicate-reported. Terminal tickets are excluded.
OPEN_STATUSES = frozenset(
    {STATUS_PENDING, STATUS_APPROVED, STATUS_IN_PROGRESS, STATUS_VERIFYING}
)

# Tokens that describe the act of complaining rather than the problem itself. They are
# ignored when comparing descriptions so a filler prefix such as "في مشكلة ..." does not
# stop duplicate detection. Values are already normalized/stemmed by tokenize_for_search.
DUPLICATE_IGNORED_TOKENS = frozenset(
    {
        "مشكله",
        "شكوى",
        "شكوه",
        "بلاغ",
        "ابلاغ",
        "مشاكل",
        "موضوع",
        "بخصوص",
    }
)

# A duplicate needs at least this many shared problem tokens. One shared word such as
# "مياه" is too weak a signal to offer a link.
MIN_DUPLICATE_SHARED_TOKENS = 2

# Default mix of Jaccard and overlap similarity; overridable through settings.
DEFAULT_DUPLICATE_THRESHOLD = 0.45

# Exact transitions from the architecture document. Declined is normally set by the
# Orchestrator during validation and is kept here so the store is the single source of truth.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_PENDING: frozenset({STATUS_APPROVED, STATUS_DISMISSED, STATUS_DECLINED}),
    STATUS_APPROVED: frozenset({STATUS_IN_PROGRESS, STATUS_DISMISSED, STATUS_DECLINED}),
    STATUS_IN_PROGRESS: frozenset({STATUS_VERIFYING, STATUS_DISMISSED, STATUS_DECLINED}),
    STATUS_VERIFYING: frozenset(
        {STATUS_DONE, STATUS_IN_PROGRESS, STATUS_DISMISSED, STATUS_DECLINED}
    ),
    STATUS_DONE: frozenset(),
    STATUS_DECLINED: frozenset(),
    STATUS_DISMISSED: frozenset(),
}


class InvalidStatusTransition(ValueError):
    """Raised when a caller tries to move a ticket along an undefined transition."""


class Ticket(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticket_id: str
    title: str
    description: str
    category: str
    authority: str
    location: dict[str, str] = Field(default_factory=dict)
    urgency: str = "medium"
    urgency_reason: str = ""
    incident_date: str | None = None
    attachments_mentioned: list[str] = Field(default_factory=list)
    contact_preference: str | None = None
    status: str = STATUS_PENDING
    created_at: str
    updated_at: str
    linked_to: str | None = None
    review_notes: list[str] = Field(default_factory=list)


class InMemoryTicketStore:
    """Thread-safe in-memory ticket repository."""

    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def _next_id(self) -> str:
        self._counter += 1
        return f"TKT-{datetime.now(UTC).year}-{self._counter:04d}"

    def create(
        self,
        *,
        title: str,
        description: str,
        category: str,
        authority: str,
        location: dict[str, str] | None = None,
        urgency: str = "medium",
        urgency_reason: str = "",
        incident_date: str | None = None,
        attachments_mentioned: list[str] | None = None,
        contact_preference: str | None = None,
        linked_to: str | None = None,
        review_notes: list[str] | None = None,
    ) -> Ticket:
        now = datetime.now(UTC).isoformat()
        with self._lock:
            ticket = Ticket(
                ticket_id=self._next_id(),
                title=title,
                description=description,
                category=category,
                authority=authority,
                location=location or {},
                urgency=urgency,
                urgency_reason=urgency_reason,
                incident_date=incident_date,
                attachments_mentioned=attachments_mentioned or [],
                contact_preference=contact_preference,
                status=STATUS_PENDING,
                created_at=now,
                updated_at=now,
                linked_to=linked_to,
                review_notes=review_notes or [],
            )
            self._tickets[ticket.ticket_id] = ticket
            return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        return self._tickets.get(ticket_id)

    def list(self) -> list[Ticket]:
        return list(self._tickets.values())

    def update_status(self, ticket_id: str, status: str) -> Ticket | None:
        """Apply a lifecycle transition, enforcing the documented state machine."""
        if status not in TICKET_STATUSES:
            raise InvalidStatusTransition(f"unknown ticket status: {status}")
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                return None
            if status == ticket.status:
                return ticket
            if status not in ALLOWED_TRANSITIONS[ticket.status]:
                raise InvalidStatusTransition(
                    f"cannot move ticket from '{ticket.status}' to '{status}'"
                )
            updated = ticket.model_copy(
                update={"status": status, "updated_at": datetime.now(UTC).isoformat()}
            )
            self._tickets[ticket_id] = updated
            return updated

    def link(self, ticket_id: str, duplicate_id: str) -> Ticket | None:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                return None
            note = f"LINKED_TO:{duplicate_id}"
            updated = ticket.model_copy(
                update={
                    "linked_to": duplicate_id,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "review_notes": [*ticket.review_notes, note],
                }
            )
            self._tickets[ticket_id] = updated
            return updated

    def add_note(self, ticket_id: str, note: str) -> Ticket | None:
        """Append a reviewer note without creating a new ticket (used for duplicate links)."""
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if not ticket:
                return None
            updated = ticket.model_copy(
                update={
                    "updated_at": datetime.now(UTC).isoformat(),
                    "review_notes": [*ticket.review_notes, note],
                }
            )
            self._tickets[ticket_id] = updated
            return updated

    def find_similar(
        self,
        *,
        category: str,
        description: str,
        location: dict[str, str] | None = None,
        threshold: float | None = None,
    ) -> tuple[Ticket, float] | None:
        """Return the most similar open ticket in the same category, if any.

        Similarity is the better of Jaccard and the overlap (containment) coefficient over
        normalized Arabic tokens. The overlap side tolerates filler prefixes, and
        ``MIN_DUPLICATE_SHARED_TOKENS`` stops a single shared word from counting as a match.
        """
        if threshold is None:
            threshold = _threshold_from_settings()
        query_tokens = _duplicate_tokens(description)
        if not query_tokens:
            return None
        location = location or {}

        best: tuple[Ticket, float] | None = None
        for ticket in self._tickets.values():
            if ticket.status not in OPEN_STATUSES or ticket.category != category:
                continue
            if not _nearby(location, ticket.location):
                continue
            other = _duplicate_tokens(ticket.description)
            if len(query_tokens & other) < MIN_DUPLICATE_SHARED_TOKENS:
                continue
            similarity = duplicate_similarity(query_tokens, other)
            if similarity >= threshold and (best is None or similarity > best[1]):
                best = (ticket, round(similarity, 4))
        return best

    def clear(self) -> None:
        with self._lock:
            self._tickets.clear()
            self._counter = 0


def _duplicate_tokens(text: str) -> set[str]:
    """Normalize a description into comparable tokens, dropping complaint filler words."""
    return set(tokenize_for_search(text or "")) - DUPLICATE_IGNORED_TOKENS


def duplicate_similarity(left: set[str], right: set[str]) -> float:
    """Return the better of Jaccard and overlap (containment) similarity.

    Jaccard punishes a longer description that carries a filler prefix, while the overlap
    coefficient compares against the shorter side and recovers that case. The overlap value
    alone would score a one-word query at 1.0, so callers also require
    ``MIN_DUPLICATE_SHARED_TOKENS`` shared tokens.
    """
    if not left or not right:
        return 0.0
    shared = len(left & right)
    if not shared:
        return 0.0
    jaccard = shared / len(left | right)
    overlap = shared / min(len(left), len(right))
    return max(jaccard, overlap)


def _threshold_from_settings() -> float:
    """Read the duplicate threshold from settings without importing it at module load."""
    from app.core.config import get_settings

    return get_settings().duplicate_similarity_threshold


def _nearby(left: dict[str, str], right: dict[str, str]) -> bool:
    """Same street, or same city/governorate when available. Unknown location is allowed."""
    for key in ("street", "city", "governorate"):
        a = (left.get(key) or "").strip()
        b = (right.get(key) or "").strip()
        if a and b:
            return a == b
    return True


def ticket_store_singleton() -> InMemoryTicketStore:
    """Process-wide store used by the API in dev/demo mode."""
    return _STORE


_STORE = InMemoryTicketStore()


def to_public_dict(ticket: Ticket) -> dict[str, Any]:
    """Serialize a ticket for the API (no internal review notes)."""
    data = ticket.model_dump(mode="json")
    data.pop("review_notes", None)
    return data

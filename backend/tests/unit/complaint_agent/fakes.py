"""Test doubles for the two external seams (LLM and RAG). No network, no keys."""

import json
import re

from app.agents.complaint_agent.schemas import RagChunk

W12 = RagChunk(
    source="Regulation W-12",
    excerpt="Emergency leaks on public mains must be repaired within 24 hours.",
)


class FakeLLM:
    """Answers each tool by looking at which system prompt it received.

    category/severity/recommendations build well-formed JSON answers.
    `raw` overrides a tool's answer: {"category": "<any text>"} returns that text unchanged
    (e.g. malformed JSON), and an Exception value is raised (provider failure).
    """

    def __init__(
        self,
        category="Water",
        severity="Critical",
        recommendations=None,
        raw=None,
        confidence="high",
        verdicts=None,
    ):
        if recommendations is None:
            recommendations = [{"text": "Repair the leak within 24 hours", "source_ids": [1]}]
        self.answers = {
            "category": {"category": category} if isinstance(category, str) else category,
            "severity": {"severity": severity, "confidence": confidence}
            if isinstance(severity, str)
            else severity,
            "recommend": {"recommendations": recommendations}
            if isinstance(recommendations, list)
            else recommendations,
        }
        self.verdicts = verdicts  # None = mark every recommendation supported
        self.answers.update(raw or {})
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        key = (
            "category"
            if "classify municipal complaints" in system
            else "severity"
            if "assign a severity" in system
            else "verify"
            if "strict reviewer" in system
            else "recommend"
        )
        if key == "verify" and "verify" not in self.answers:
            indexes = [int(n) for n in re.findall(r"^R(\d+):", user, re.MULTILINE)]
            self.answers["verify"] = {
                "verdicts": self.verdicts
                if self.verdicts is not None
                else [{"index": n, "supported": True} for n in indexes]
            }
        answer = self.answers[key]
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer)


class FakeRag:
    def __init__(self, chunks=None, error: Exception | None = None):
        self.chunks = [W12] if chunks is None else chunks
        self.error = error
        self.calls: list[tuple[str, str, int]] = []

    def retrieve(self, query, category, top_k=5):
        self.calls.append((query, category, top_k))
        if self.error:
            raise self.error
        return self.chunks


def make_state(description="Pipe leakage near street", authority="Water", **over):
    state = {
        "ticket_id": "C123",
        "status": "Processing",
        "payload": {
            "authority": authority,
            "description": description,
            "location": {"lat": 30.0444, "lon": 31.2357},
            "citizen": {"name": "Ahmed Ali", "national_id": "29812345678901"},
            "attachments": [{"file_id": "IMG_001", "type": "image/jpeg"}],
        },
        "severity": None,
        "recommendations": [],
        "tool_calls": 0,
        "tool_call_limit": 8,
    }
    state.update(over)
    return state

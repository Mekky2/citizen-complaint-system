"""Recommendation grounding.

Layers: (1) cited sources must exist, (2) written references must appear in the cited text,
(3) a verifier LLM call judges support. The verifier is MOCKED here: these tests prove the
agent obeys its verdicts and fails closed. They do not prove the real verifier is accurate;
that is only measured with a live key, and even then it is an LLM judging an LLM.
"""

import pytest

from app.agents.complaint_agent import run_complaint_agent
from app.agents.complaint_agent.schemas import RagChunk
from tests.unit.complaint_agent.fakes import W12, FakeLLM, FakeRag, make_state

TWO_RECS = [
    {"text": "Repair the leak within 24 hours", "source_ids": [1]},
    {"text": "Notify the water supervisor", "source_ids": [1]},
]
ELECTRICITY_CHUNK = RagChunk(
    source="Regulation E-3", excerpt="Exposed conductors must be isolated immediately."
)


def codes(out):
    return [n.split(":")[0] for n in out["review_notes"]]


def test_only_recommendations_the_verifier_supports_are_kept():
    llm = FakeLLM(
        recommendations=TWO_RECS,
        verdicts=[{"index": 1, "supported": True}, {"index": 2, "supported": False}],
    )
    out = run_complaint_agent(make_state(), llm, FakeRag())
    assert out["recommendations"] == ["Repair the leak within 24 hours [Source: Regulation W-12]"]
    assert "RECOMMENDATIONS_REMOVED" in codes(out)


def test_verifier_receives_sources_and_recommendations():
    llm = FakeLLM(recommendations=TWO_RECS)
    run_complaint_agent(make_state(), llm, FakeRag())
    system, user = llm.calls[-1]
    assert "strict reviewer" in system
    assert W12.excerpt in user and "R1: Repair the leak" in user and "R2: Notify" in user


def test_missing_verdict_fails_closed():
    llm = FakeLLM(recommendations=TWO_RECS, verdicts=[{"index": 1, "supported": True}])
    out = run_complaint_agent(make_state(), llm, FakeRag())
    assert len(out["recommendations"]) == 1  # R2 had no verdict -> dropped


def test_all_unsupported_gives_no_recommendations_and_explains_why():
    llm = FakeLLM(verdicts=[{"index": 1, "supported": False}])
    out = run_complaint_agent(make_state(), llm, FakeRag())
    assert out["status"] == "Completed" and out["recommendations"] == []
    assert "NO_SUPPORTED_RECOMMENDATIONS" in codes(out)
    assert out["rag_context"] == [W12.model_dump()]  # evidence is still shown to the reviewer


def test_irrelevant_evidence_yields_no_recommendation():
    # Water complaint, but retrieval returned an electricity regulation; the generator
    # (following its prompt) returns nothing.
    llm = FakeLLM(recommendations=[])
    out = run_complaint_agent(make_state(), llm, FakeRag(chunks=[ELECTRICITY_CHUNK]))
    assert out["recommendations"] == []
    assert "NO_SUPPORTED_RECOMMENDATIONS" in codes(out)
    assert out["tool_calls"] == 4  # verifier not called when there is nothing to verify


def test_no_evidence_is_explained():
    out = run_complaint_agent(make_state(), FakeLLM(), FakeRag(chunks=[]))
    assert out["recommendations"] == [] and codes(out) == ["NO_RETRIEVED_EVIDENCE"]


def test_verifier_provider_error_fails_the_ticket_instead_of_trusting_drafts():
    llm = FakeLLM(raw={"verify": TimeoutError("slow")})
    out = run_complaint_agent(make_state(), llm, FakeRag())
    assert out["status"] == "Failed" and out["failure_reason"] == "LLM_PROVIDER_ERROR"
    assert out["recommendations"] == []  # drafts are never released unverified
    assert out["category"] == "Water" and out["severity"] == "Critical"


@pytest.mark.parametrize("raw", ["nope", '{"verdicts": "yes"}', '{"verdicts": [{"index": "a"}]}'])
def test_malformed_verifier_response_fails_the_ticket(raw):
    out = run_complaint_agent(make_state(), FakeLLM(raw={"verify": raw}), FakeRag())
    assert out["failure_reason"] == "MALFORMED_LLM_RESPONSE" and out["recommendations"] == []


def test_tool_call_limit_reached_before_verification_fails_closed():
    out = run_complaint_agent(make_state(tool_calls=3, tool_call_limit=7), FakeLLM(), FakeRag())
    assert out["failure_reason"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert out["recommendations"] == [] and out["tool_calls"] == 7


def test_invented_reference_is_removed_before_verification():
    recs = [{"text": "Apply Article 99 immediately", "source_ids": [1]}]
    llm = FakeLLM(recommendations=recs)
    out = run_complaint_agent(make_state(), llm, FakeRag())
    assert out["recommendations"] == [] and "RECOMMENDATIONS_REMOVED" in codes(out)
    assert out["tool_calls"] == 4  # nothing survived layer 2, so no verifier call


def test_source_attribution_is_preserved_for_multiple_sources():
    recs = [{"text": "Isolate the conductors now", "source_ids": [1, 2]}]
    chunks = [ELECTRICITY_CHUNK, W12]
    out = run_complaint_agent(make_state(), FakeLLM(recommendations=recs), FakeRag(chunks=chunks))
    assert out["recommendations"] == [
        "Isolate the conductors now [Source: Regulation E-3; Regulation W-12]"
    ]
    assert out["rag_context"] == [c.model_dump() for c in chunks]

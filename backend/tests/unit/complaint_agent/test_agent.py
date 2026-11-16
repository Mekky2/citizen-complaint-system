import copy

import pytest

from app.agents.complaint_agent import run_complaint_agent
from app.agents.complaint_agent.schemas import RagChunk
from tests.unit.complaint_agent.fakes import W12, FakeLLM, FakeRag, make_state


# --- success contract -----------------------------------------------------------
def test_success_output_has_documented_fields_and_values():
    out = run_complaint_agent(make_state(), FakeLLM(), FakeRag())
    assert set(out) == {
        "ticket_id",
        "status",
        "payload",
        "category",
        "severity",
        "recommendations",
        "rag_context",
        "tool_calls",
        "review_notes",  # extension, see AgentSuccess
    }
    assert out["status"] == "Completed"
    assert out["category"] == "Water" and out["severity"] == "Critical"
    assert out["tool_calls"] == 5  # categorize, severity, rag, generate, verify
    assert out["review_notes"] == []
    assert out["rag_context"] == [W12.model_dump()]


def test_payload_and_ticket_id_preserved_exactly():
    state = make_state()
    original = copy.deepcopy(state["payload"])
    out = run_complaint_agent(state, FakeLLM(), FakeRag())
    assert out["payload"] == original and out["ticket_id"] == "C123"
    assert state["payload"] == original  # input not mutated


def test_incoming_tool_calls_counter_is_continued_not_reset():
    out = run_complaint_agent(make_state(tool_calls=2), FakeLLM(), FakeRag())
    assert out["tool_calls"] == 7


# --- grounding -------------------------------------------------------------------
def test_every_recommendation_carries_its_source():
    out = run_complaint_agent(make_state(), FakeLLM(), FakeRag())
    assert out["recommendations"] == ["Repair the leak within 24 hours [Source: Regulation W-12]"]


def test_empty_rag_context_gives_no_recommendations_and_skips_llm_call():
    llm = FakeLLM()
    out = run_complaint_agent(make_state(), llm, FakeRag(chunks=[]))
    assert out["status"] == "Completed"
    assert out["recommendations"] == [] and out["rag_context"] == []
    assert out["tool_calls"] == 3  # categorize, severity, rag; no generator call
    assert len(llm.calls) == 2


def test_recommendation_citing_unretrieved_source_is_dropped():
    recs = [{"text": "Do something", "source_ids": [7]}]
    out = run_complaint_agent(make_state(), FakeLLM(recommendations=recs), FakeRag())
    assert out["status"] == "Completed" and out["recommendations"] == []


def test_recommendation_without_source_ids_is_a_malformed_response():
    recs = [{"text": "Do something", "source_ids": []}]
    out = run_complaint_agent(make_state(), FakeLLM(recommendations=recs), FakeRag())
    assert out["status"] == "Failed" and out["failure_reason"] == "MALFORMED_LLM_RESPONSE"


@pytest.mark.parametrize(
    "text",
    [
        "Follow Article 99 of the Water Law",
        "Apply regulation W-13 immediately",
        "See Regulation X-1",
    ],
)
def test_invented_legal_reference_is_dropped(text):
    recs = [{"text": text, "source_ids": [1]}]
    out = run_complaint_agent(make_state(), FakeLLM(recommendations=recs), FakeRag())
    assert out["recommendations"] == []


def test_reference_present_in_source_is_kept():
    recs = [{"text": "Follow regulation W-12 for emergency leaks", "source_ids": [1]}]
    out = run_complaint_agent(make_state(), FakeLLM(recommendations=recs), FakeRag())
    assert len(out["recommendations"]) == 1


def test_source_and_excerpt_are_not_altered():
    chunk = RagChunk(source="Law 4/1994 Art. 7", excerpt="Original excerpt text.")
    out = run_complaint_agent(make_state(), FakeLLM(), FakeRag(chunks=[chunk]))
    assert out["rag_context"] == [
        {"source": "Law 4/1994 Art. 7", "excerpt": "Original excerpt text."}
    ]


# --- failure contract ------------------------------------------------------------
def test_rag_failure_returns_failed_with_partial_results():
    out = run_complaint_agent(make_state(), FakeLLM(), FakeRag(error=ConnectionError("db down")))
    assert out["status"] == "Failed" and out["failure_reason"] == "RAG_UNAVAILABLE"
    assert out["category"] == "Water" and out["severity"] == "Critical"
    assert out["recommendations"] == [] and out["tool_calls"] == 3
    assert set(out) == {
        "ticket_id",
        "status",
        "failure_reason",
        "category",
        "severity",
        "recommendations",
        "tool_calls",
    }


def test_malformed_rag_items_are_a_rag_failure():
    out = run_complaint_agent(
        make_state(), FakeLLM(), FakeRag(chunks=[{"source": "", "excerpt": ""}])
    )
    assert out["failure_reason"] == "RAG_UNAVAILABLE"


@pytest.mark.parametrize(
    "raw", ["not json at all", "{broken", "[]", '{"category": 5}', '{"cat": "Water"}', ""]
)
def test_malformed_llm_response_returns_failed(raw):
    out = run_complaint_agent(make_state(), FakeLLM(raw={"category": raw}), FakeRag())
    assert out["status"] == "Failed" and out["failure_reason"] == "MALFORMED_LLM_RESPONSE"
    assert out["category"] is None and out["tool_calls"] == 1


def test_json_inside_markdown_fence_is_accepted():
    fenced = '```json\n{"category": "Water"}\n```'
    out = run_complaint_agent(make_state(), FakeLLM(raw={"category": fenced}), FakeRag())
    assert out["status"] == "Completed"


def test_llm_provider_error_returns_failed_and_keeps_category():
    out = run_complaint_agent(
        make_state(), FakeLLM(raw={"severity": TimeoutError("slow")}), FakeRag()
    )
    assert out["failure_reason"] == "LLM_PROVIDER_ERROR"
    assert out["category"] == "Water" and out["severity"] is None and out["tool_calls"] == 2


def test_invalid_severity_value_is_rejected():
    out = run_complaint_agent(make_state(), FakeLLM(severity="Urgent"), FakeRag())
    assert out["failure_reason"] == "MALFORMED_LLM_RESPONSE"


def test_tool_call_limit_stops_the_agent_and_keeps_partial_results():
    out = run_complaint_agent(make_state(tool_calls=1, tool_call_limit=2), FakeLLM(), FakeRag())
    assert out["failure_reason"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert out["category"] == "Water" and out["tool_calls"] == 2


def test_limit_already_reached_makes_no_calls():
    llm = FakeLLM()
    out = run_complaint_agent(make_state(tool_calls=8), llm, FakeRag())
    assert out["failure_reason"] == "TOOL_CALL_LIMIT_EXCEEDED"
    assert llm.calls == [] and out["tool_calls"] == 8


@pytest.mark.parametrize(
    "state",
    [{}, {"ticket_id": "C9"}, make_state(description="   "), make_state(authority="Pizza")],
)
def test_invalid_input_returns_failed_never_raises(state):
    out = run_complaint_agent(state, FakeLLM(), FakeRag())
    assert out["status"] == "Failed" and out["failure_reason"] == "INVALID_INPUT"


def test_failure_keeps_ticket_id_and_counter_for_bad_payload():
    out = run_complaint_agent(make_state(description="", tool_calls=3), FakeLLM(), FakeRag())
    assert out["ticket_id"] == "C123" and out["tool_calls"] == 3


# --- categorization / ambiguity ----------------------------------------------------
def test_unclear_category_falls_back_to_authority():
    out = run_complaint_agent(
        make_state("help", authority="Roads"), FakeLLM(category="Unclear"), FakeRag()
    )
    assert out["category"] == "Roads"


def test_invented_category_is_rejected():
    out = run_complaint_agent(make_state(), FakeLLM(category="Pizza"), FakeRag())
    assert out["failure_reason"] == "MALFORMED_LLM_RESPONSE"


def test_confident_category_differing_from_authority_is_returned():
    state = make_state("Garbage piled up for a week", authority="Water")
    out = run_complaint_agent(state, FakeLLM(category="Environment"), FakeRag())
    assert out["category"] == "Environment"


# --- privacy -----------------------------------------------------------------------
def test_no_citizen_pii_is_sent_to_llm_or_rag():
    llm, rag = FakeLLM(), FakeRag()
    run_complaint_agent(make_state(), llm, rag)
    sent = " ".join(s + u for s, u in llm.calls) + " ".join(str(c) for c in rag.calls)
    for secret in ("Ahmed", "29812345678901", "30.0444", "IMG_001"):
        assert secret not in sent


# --- languages -----------------------------------------------------------------------
@pytest.mark.parametrize(
    "description",
    ["Pipe leakage near street", "فيه ماسورة مكسورة والمية بتغرق الشارع"],
)
def test_english_and_egyptian_arabic_descriptions_flow_through(description):
    llm = FakeLLM()
    out = run_complaint_agent(make_state(description), llm, FakeRag())
    assert out["status"] == "Completed"
    assert description in llm.calls[0][1]  # sent verbatim, not translated or altered

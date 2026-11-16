"""Contract test: the agent's output must match docs/system_architecture.md exactly and
must be usable as the Orchestrator's state (same keys the LangGraph state reads)."""

from app.agents.complaint_agent import run_complaint_agent
from app.agents.complaint_agent.schemas import AgentFailure, AgentSuccess
from tests.unit.complaint_agent.fakes import FakeLLM, FakeRag, make_state

# Keys copied from the documented success / failure JSON examples.
DOC_SUCCESS_KEYS = {
    "ticket_id",
    "status",
    "payload",
    "category",
    "severity",
    "recommendations",
    "rag_context",
    "tool_calls",
}
DOC_FAILURE_KEYS = {
    "ticket_id",
    "status",
    "failure_reason",
    "category",
    "severity",
    "recommendations",
    "tool_calls",
}


def test_success_matches_documented_contract_and_roundtrips():
    out = run_complaint_agent(make_state(), FakeLLM(), FakeRag())
    # Documented keys are all present; `review_notes` is the one proposed extension.
    assert set(out) == DOC_SUCCESS_KEYS | {"review_notes"}
    assert AgentSuccess.model_validate(out).model_dump(mode="json") == out
    assert all(set(c) == {"source", "excerpt"} for c in out["rag_context"])


def test_failure_matches_documented_contract_and_roundtrips():
    out = run_complaint_agent(make_state(tool_calls=8), FakeLLM(), FakeRag())
    assert set(out) == DOC_FAILURE_KEYS
    assert out["failure_reason"] == "TOOL_CALL_LIMIT_EXCEEDED"  # the documented example reason
    assert AgentFailure.model_validate(out).model_dump(mode="json") == out


def test_agent_statuses_are_only_the_documented_ones():
    ok = run_complaint_agent(make_state(), FakeLLM(), FakeRag())
    bad = run_complaint_agent({}, FakeLLM(), FakeRag())
    assert {ok["status"], bad["status"]} <= {"Processing", "Completed", "Failed"}


def test_output_is_json_serialisable():
    import json

    json.dumps(run_complaint_agent(make_state(), FakeLLM(), FakeRag()), ensure_ascii=False)

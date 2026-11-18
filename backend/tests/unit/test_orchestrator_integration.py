"""The orchestrator node now calls the real agent instead of returning placeholders."""

from __future__ import annotations

from app.agents.complaint_agent.schemas import CATEGORIES, SEVERITIES
from app.agents.orchestrator.middleware import validate_ticket
from app.agents.orchestrator.orchestrator import route_department, send_to_complaint_agent
from app.agents.orchestrator.rag_adapter import KnowledgeBaseRetriever
from app.knowledge_base import HashingEmbeddingProvider, InMemoryKnowledgeBase
from app.services.llm_gateway import LLMGateway
from app.services.observability import reset_trace


class AlwaysFail:
    def complete(self, system: str, user: str) -> str:
        raise RuntimeError("provider down")


def _state(**overrides):
    state = {
        "ticket_id": "T-1",
        "status": "Processing",
        "payload": {
            "authority": "Water",
            "description": "تسريب مياه في ماسورة رئيسية أمام المدرسة",
            "location": {"lat": 0.0, "lon": 0.0},
            "citizen": {"name": "Ahmed", "national_id": "29812345678901"},
        },
        "severity": None,
        "recommendations": [],
        "tool_calls": 0,
        "error": None,
        "assigned_department": None,
    }
    state.update(overrides)
    return state


def _retriever() -> KnowledgeBaseRetriever:
    from pathlib import Path

    backend = Path(__file__).resolve().parents[2]
    kb = InMemoryKnowledgeBase(HashingEmbeddingProvider(1024))
    kb.ingest_directory(str(backend / "data" / "knowledge"))
    return KnowledgeBaseRetriever(kb)


def test_offline_gateway_still_produces_a_structured_analysis():
    reset_trace()
    gateway = LLMGateway([], offline=None)  # no providers, no offline -> failure path
    result = send_to_complaint_agent(_state(), llm=gateway, rag=_retriever())

    assert result["status"] == "ComplaintFailed"
    assert result["error"] in {"LLM_PROVIDER_ERROR", "MALFORMED_LLM_RESPONSE"}
    assert result["severity"] is None
    assert result["recommendations"] == []


def test_offline_rules_produce_a_grounded_analysis():
    from app.services.offline_llm import GroundedTemplateLLM, OfflineToolLLM

    reset_trace()
    gateway = LLMGateway(
        [], offline=OfflineToolLLM(GroundedTemplateLLM()), max_attempts=1
    )
    result = send_to_complaint_agent(_state(), llm=gateway, rag=_retriever())

    assert result["status"] == "ComplaintAnalyzed"
    assert result["severity"] in SEVERITIES
    assert result["category"] in CATEGORIES
    assert result["recommendations"], "a grounded recommendation must survive offline mode"
    assert "Source:" in result["recommendations"][0]
    # No invented 24-hour deadline from the old placeholder.
    assert "24h" not in " ".join(result["recommendations"])


def test_national_id_never_reaches_the_agent():
    from app.services.offline_llm import GroundedTemplateLLM, OfflineToolLLM

    reset_trace()
    gateway = LLMGateway([], offline=OfflineToolLLM(GroundedTemplateLLM()))
    result = send_to_complaint_agent(_state(), llm=gateway, rag=_retriever())

    assert "national_id" not in result["payload"]["citizen"]
    assert result["payload"]["citizen"].get("name") == "Ahmed"


def test_failed_llm_is_reported_not_raised():
    reset_trace()
    result = send_to_complaint_agent(_state(), llm=AlwaysFail(), rag=_retriever())

    assert result["status"] == "ComplaintFailed"
    assert result["error"] == "LLM_PROVIDER_ERROR"
    assert result["severity"] is None
    assert result["status"] != "Critical"


def test_route_department_still_maps_every_category():
    assert route_department(_state())["assigned_department"] == "water_dashboard"
    roads = _state()
    roads["payload"]["authority"] = "Roads"
    assert route_department(roads)["assigned_department"] == "roads_dashboard"


def test_identity_fields_are_optional_but_checked_when_present():
    state = _state()
    assert validate_ticket(state) is state  # unchanged object, no mutation

    without_citizen = _state()
    without_citizen["payload"]["citizen"] = {}
    assert validate_ticket(without_citizen) is without_citizen

    empty_name = _state()
    empty_name["payload"]["citizen"] = {"name": "", "national_id": "1"}
    try:
        validate_ticket(empty_name)
    except ValueError as exc:
        assert "name" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("an explicitly empty name must be rejected")

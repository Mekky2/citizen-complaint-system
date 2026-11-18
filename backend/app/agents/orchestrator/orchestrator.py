"""Orchestrator nodes.

The public functions keep their original names and signatures. The only behaviour that
changed is inside ``send_to_complaint_agent``: the placeholder that returned a hardcoded
``severity="Critical"`` and ``"Immediate repair required within 24h"`` now calls the real
Complaint Agent through the shared LLM gateway.
"""

from __future__ import annotations

from typing import Any

from app.agents.complaint_agent.agent import run_complaint_agent
from app.agents.orchestrator.state import OrchestratorState


def _strip_pii(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop the national ID before the payload reaches an LLM or a log.

    The agent never needs identity data; keeping it only increases the blast radius of a
    prompt-injection or a log leak. Other fields are preserved exactly.
    """
    cleaned = dict(payload)
    citizen = dict(cleaned.get("citizen") or {})
    citizen.pop("national_id", None)
    cleaned["citizen"] = citizen
    return cleaned


def send_to_complaint_agent(
    state: OrchestratorState,
    *,
    llm: Any | None = None,
    rag: Any | None = None,
) -> dict[str, Any]:
    """Run the structured Complaint Agent and merge its answer into the orchestrator state.

    ``llm`` and ``rag`` are optional so tests can inject fakes. Production passes nothing and
    the runtime gateway/retriever are used. Failures are returned as structured state (never
    raised) because the orchestrator graph must be able to continue to the dashboard/decline
    step.
    """
    from app.services.runtime import get_runtime

    runtime = get_runtime()
    llm = llm or runtime.gateway
    rag = rag or runtime.rag_retriever()

    payload = _strip_pii(dict(state.get("payload") or {}))
    agent_state = {
        "ticket_id": str(state.get("ticket_id") or "UNKNOWN"),
        "status": "Processing",
        "payload": payload,
        "severity": state.get("severity"),
        "recommendations": list(state.get("recommendations") or []),
        "tool_calls": int(state.get("tool_calls") or 0),
        "tool_call_limit": runtime.settings.tool_call_limit_per_ticket,
    }

    result = run_complaint_agent(agent_state, llm, rag)
    base = {**state, "payload": payload}

    if result.get("status") == "Completed":
        return {
            **base,
            "severity": result.get("severity"),
            "recommendations": list(result.get("recommendations") or []),
            "tool_calls": int(result.get("tool_calls") or 0),
            "status": "ComplaintAnalyzed",
            "error": None,
            # Extensions for the dashboard/API; ignored by callers that only read severity.
            "category": result.get("category"),
            "rag_context": result.get("rag_context") or [],
            "review_notes": result.get("review_notes") or [],
        }

    return {
        **base,
        "severity": None,
        "recommendations": [],
        "tool_calls": int(result.get("tool_calls") or 0),
        "status": "ComplaintFailed",
        "error": result.get("failure_reason") or "UNKNOWN_FAILURE",
        "category": result.get("category"),
        "rag_context": [],
        "review_notes": [],
    }


def route_department(state: OrchestratorState):
    """
    Routes complaint to correct dashboard.
    """

    authority = state["payload"]["authority"]

    department_map = {
        "Water": "water_dashboard",
        "Electricity": "electricity_dashboard",
        "Roads": "roads_dashboard",
        "Environment": "environment_dashboard",
    }

    assigned_department = department_map.get(authority, "general_dashboard")

    return {**state, "assigned_department": assigned_department, "status": "AssignedToDepartment"}

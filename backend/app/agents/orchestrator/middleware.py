from app.agents.orchestrator.state import OrchestratorState

VALID_AUTHORITIES = ["Water", "Electricity", "Roads", "Environment"]


def validate_ticket(state: OrchestratorState):
    """Validate the fields the agents actually need.

    Identity data is optional and never required: the citizen-facing agent deliberately does
    not collect a national ID and masks any digits it receives (PII minimisation). When the
    fields are present they are still checked, so existing callers behave as before. This
    function never mutates the state, so it stays safe to reuse the caller's object.
    """

    payload = state["payload"]

    if not payload.get("description"):
        raise ValueError("Description is required")

    if payload.get("authority") not in VALID_AUTHORITIES:
        raise ValueError("Invalid authority")

    citizen = payload.get("citizen") or {}
    if "name" in citizen and not citizen["name"]:
        raise ValueError("Citizen name cannot be empty when provided")

    if "national_id" in citizen and not citizen["national_id"]:
        raise ValueError("National ID cannot be empty when provided")

    return state

from state import OrchestratorState


VALID_AUTHORITIES = [
    "Water",
    "Electricity",
    "Roads",
    "Environment"
]


def validate_ticket(state: OrchestratorState):
    
    payload = state["payload"]

    if not payload["description"]:
        raise ValueError("Description is required")

    if payload["authority"] not in VALID_AUTHORITIES:
        raise ValueError("Invalid authority")

    citizen = payload["citizen"]

    if not citizen["name"]:
        raise ValueError("Citizen name is required")

    if not citizen["national_id"]:
        raise ValueError("National ID is required")

    return state
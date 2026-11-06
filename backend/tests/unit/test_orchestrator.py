import pytest

from app.agents.orchestrator.middleware import validate_ticket


def test_validation_success():
    state = {
        "ticket_id": "1",
        "status": "Processing",
        "payload": {
            "authority": "Water",
            "description": "Pipe leakage",
            "citizen": {
                "name": "Ahmed",
                "national_id": "123456",
            },
        },
        "severity": None,
        "recommendations": [],
        "tool_calls": 0,
        "error": None,
        "assigned_department": None,
    }

    result = validate_ticket(state)

    assert result == state


def test_invalid_authority():
    state = {
        "ticket_id": "1",
        "status": "Processing",
        "payload": {
            "authority": "Pizza",
            "description": "Pipe leakage",
            "citizen": {
                "name": "Ahmed",
                "national_id": "123456",
            },
        },
        "severity": None,
        "recommendations": [],
        "tool_calls": 0,
        "error": None,
        "assigned_department": None,
    }

    with pytest.raises(ValueError):
        validate_ticket(state)

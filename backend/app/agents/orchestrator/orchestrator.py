from state import OrchestratorState


def send_to_complaint_agent(
    state: OrchestratorState
):
    """
    Placeholder for future Complaint Agent call.
    """

    print(
        "Sending complaint to Complaint Agent..."
    )

    return {
        **state,
        "severity": "Critical",
        "recommendations": [
            "Immediate repair required within 24h"
        ],
        "tool_calls": 3,
        "status": "ComplaintAnalyzed"
    }


def route_department(
    state: OrchestratorState
):
    """
    Routes complaint to correct dashboard.
    """

    authority = (
        state["payload"]["authority"]
    )

    department_map = {
        "Water": "water_dashboard",
        "Electricity": "electricity_dashboard",
        "Roads": "roads_dashboard",
        "Environment": "environment_dashboard"
    }

    assigned_department = (
        department_map.get(
            authority,
            "general_dashboard"
        )
    )

    print(
        f"Routed to {assigned_department}"
    )

    return {
    **state,
    "assigned_department": assigned_department,
    "status": "AssignedToDepartment"
}

#response = complaint_agent.invoke(state)
from langgraph.graph import (
    StateGraph,
    START,
    END
)

from state import (
    OrchestratorState
)

from middleware import (
    validate_ticket
)

from orchestrator import (
    send_to_complaint_agent,
    route_department
)


builder = StateGraph(
    OrchestratorState
)

builder.add_node(
    "validation",
    validate_ticket
)

builder.add_node(
    "complaint_agent",
    send_to_complaint_agent
)

builder.add_node(
    "route_department",
    route_department
)

builder.add_edge(
    START,
    "validation"
)

builder.add_edge(
    "validation",
    "complaint_agent"
)

builder.add_edge(
    "complaint_agent",
    "route_department"
)

builder.add_edge(
    "route_department",
    END
)

graph = builder.compile()




# START
#   ↓
# Validation
#   ↓
# Complaint Agent
#   ↓
# Route Department
#   ↓
# END
# test_graph.py

from graph import graph

sample_ticket = {
    "ticket_id": "C123",
    "status": "Processing",
    "payload": {
        "authority": "Water",
        "description": "Pipe leakage near street",
        "citizen": {
            "name": "Ahmed Ali",
            "national_id": "29812345678901"
        }
    },
    "severity": None,
    "recommendations": [],
    "tool_calls": 0,
    "error": None
}

result = graph.invoke(sample_ticket)

print(result)
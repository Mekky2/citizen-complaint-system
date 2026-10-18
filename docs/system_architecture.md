# Citizen Complaint Management System - Architecture

## High-Level Architecture

The system utilizes a multi-agent LLM architecture combined with a human-operator dashboard and embedded analytics.

**Core Components:**

1. **Citizen Interface:** Web portal with (a) the complaint submission form (with optional photo attachments) and (b) a ticket tracking page driven by the Ticket ID. It has no in-app notifications.
2. **Orchestrator (Supervisor Agent):** The central hub. It receives the JSON payload from the user, runs the **validation step** (required fields and authority/content consistency), handles middleware (Tool Retry, PII masking, Logging, Tool Call Limits), and routes data to specialized agents or the dashboard update tool. Tickets that fail validation are **declined** here and never reach the dashboard.
3. **Complaint Agent:** The analytical engine. It receives tasks from the Orchestrator and utilizes specific tools:
   * *Categorization Tool (LLM):* Assigns the problem type (e.g., Water, Electricity, Roads, Garbage).
   * *Severity Classifier Tool (LLM):* Assigns priority/severity (e.g., Critical, Medium, Weak).
   * *RAG Retrieval Tool (Knowledge Base):* Pulls relevant policies, laws, and regulations based on the category and text. The knowledge base is fed and maintained by the development team.
   * *Recommendation Generator Tool:* Formulates suggested actions combining the severity and retrieved laws.
4. **Dashboard & Workflow System:** The human-facing interface managing the ticket state machine, including the proof-rejection loop (`Verifying → In Progress`). It also provides **in-app notifications for dashboard users only** (reviewers, maintenance teams).
5. **Embedded Analytics AI & Analyzer:** Compiles tickets, analyzes data, and generates graphs/insights for administration.

## Status Model

There are two separate status layers. They must not be mixed.

### 1. Agent processing status (internal, Orchestrator <-> Complaint Agent only)

| Status | Meaning |
|---|---|
| `Processing` | Orchestrator handed the ticket to the Complaint Agent. |
| `Completed` | Agent finished with severity and recommendations. |
| `Failed` | Agent could not finish (tool-call limit hit, repeated tool failure, timeout). |

### 2. Ticket lifecycle status (visible to dashboard users and the citizen tracking page)

| Status | Set by | Meaning |
|---|---|---|
| `Declined` | Orchestrator | Failed validation (missing data or wrong authority). Terminal, never reaches the dashboard. A reason is shown to the citizen. |
| `Pending` | Orchestrator | Analyzed and routed; waiting for reviewer decision. |
| `Approved` | Reviewer | Complaint accepted as legitimate; waiting for team assignment. |
| `Dismissed` | Reviewer | Invalid or duplicate complaint. Terminal. |
| `In Progress` | Reviewer (on team assignment) | Maintenance team assigned and working. |
| `Verifying` | Maintenance team (marks task "Completed") | Proof uploaded; waiting for admin verification. |
| `Done` | Admin | Proof confirmed; ticket closed. |

**Proof rejection:** If the admin finds the proof insufficient, they reject it with a short note and the ticket returns from `Verifying` to `In Progress` for the same maintenance team. The team is notified in-app, re-does or re-documents the work, uploads new proof, and marks it "Completed" again, moving the ticket back to `Verifying`. This loop can repeat until the admin confirms.

Happy path: `Pending → Approved → In Progress → Verifying → Done`

Rework loop: `Verifying → In Progress` (proof rejected by admin)

### Mapping between the two layers

| Agent result | Ticket lifecycle status set by Orchestrator |
|---|---|
| `Completed` | `Pending` (routed to the department dashboard) |
| `Failed` | `Pending`, flagged **"Needs manual review"** with severity `Unclassified`. The human reviewer handles it. |
| (validation fails before the agent runs) | `Declined` |

## Tool Call Limiting

Goals: prevent runaway loops and cost, keep latency bounded, and never lose a citizen's ticket because of an AI failure.

| Control | Value (configurable) |
|---|---|
| Max tool calls per ticket (all attempts, including retries) | **8** (happy path uses 4) |
| Max calls per individual tool (first attempt + retries) | **3** |
| Retry policy | Retry only transient errors (timeouts, 5xx, rate limits); exponential backoff with jitter (e.g., 1s, 2s); never retry validation/4xx errors |
| Per-tool timeout | 15 seconds |
| Per-ticket total timeout | 60 seconds |
| Loop guard | Same tool with identical arguments twice in a row is blocked |
| Circuit breaker | If a tool fails repeatedly across tickets, stop calling it for a cool-down period and use the fallback |

**When a limit is exceeded:**
1. The Orchestrator stops further tool calls and sets the agent status to `Failed`, keeping any partial results (e.g., category already found).
2. The ticket is still routed to the dashboard as `Pending`, flagged "Needs manual review" with severity `Unclassified`.
3. The event is logged for audit and monitoring.

The `tool_calls` counter in the payload tracks every invocation, including retries, and is enforced by the Orchestrator middleware, not by the LLM.

## Agent State & Payload Specifications

### Input: Orchestrator -> Complaint Agent

```json
{
  "ticket_id": "C123",
  "status": "Processing",
  "payload": {
    "authority": "Water",
    "description": "Pipe leakage near street",
    "location": {"lat": 30.0444, "lon": 31.2357},
    "citizen": {
      "name": "Ahmed Ali",
      "national_id": "29812345678901"
    },
    "attachments": [
      {"file_id": "IMG_001", "type": "image/jpeg"}
    ]
  },
  "severity": null,
  "recommendations": [],
  "tool_calls": 0,
  "tool_call_limit": 8
}
```

### Output: Complaint Agent -> Orchestrator (Structured Output)

```json
{
  "ticket_id": "C123",
  "status": "Completed",
  "payload": {
    "authority": "Water",
    "description": "Pipe leakage near street",
    "location": {"lat": 30.0444, "lon": 31.2357},
    "citizen": {
      "name": "Ahmed Ali",
      "national_id": "29812345678901"
    },
    "attachments": [
      {"file_id": "IMG_001", "type": "image/jpeg"}
    ]
  },
  "category": "Water",
  "severity": "Critical",
  "recommendations": [
    "Immediate repair required within 24h",
    "Notify water department supervisor",
    "Follow regulation W-12 for emergency leaks"
  ],
  "rag_context": [
    {"source": "Regulation W-12", "excerpt": "..."}
  ],
  "tool_calls": 4
}
```

### Output on failure: Complaint Agent -> Orchestrator

```json
{
  "ticket_id": "C124",
  "status": "Failed",
  "failure_reason": "TOOL_CALL_LIMIT_EXCEEDED",
  "category": "Roads",
  "severity": null,
  "recommendations": [],
  "tool_calls": 8
}
```

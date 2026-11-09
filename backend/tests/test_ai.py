"""
AI integration: run creation, callback validation, idempotency, invalid AI
response, Legal RAG search (FIX 3), Similar Cases privacy (FIX 4), and
Legal Evidence vs Similar Case separation.
"""

import uuid

from app.models.ai import AiRun
from app.models.enums import AiRunStatus
from app.models.rag import LegalKnowledgeChunk, LegalKnowledgeDocument
from app.models.ticket import Ticket
from tests.conftest import auth_headers, create_pending_ai_run


def _create_ticket(client, token):
    resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token),
        json={"description": "AI test ticket about a broken streetlight", "lat": 30.2, "lng": 31.2},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_ai_run_creation_requires_staff_role(client, citizen_token):
    ticket_id = _create_ticket(client, citizen_token)
    resp = client.post(
        f"/api/v1/ai/tickets/{ticket_id}/trigger", headers=auth_headers(citizen_token)
    )
    assert resp.status_code == 403  # citizens cannot trigger AI review


def test_ai_run_creation_by_supervisor(client, citizen_token, supervisor_token):
    ticket_id = _create_ticket(client, citizen_token)
    resp = client.post(
        f"/api/v1/ai/tickets/{ticket_id}/trigger", headers=auth_headers(supervisor_token)
    )
    assert resp.status_code == 201
    assert resp.json()["ticket_id"] == ticket_id


def test_recommendations_endpoint_requires_shared_secret(client, citizen_token, db):
    ticket_id = _create_ticket(client, citizen_token)
    run_id = create_pending_ai_run(db, ticket_id)
    resp = client.post(
        "/api/v1/ai/recommendations",
        json={
            "run_id": run_id,
            "ticket_id": ticket_id,
            "status": "succeeded",
            "recommendation": {"severity": "low"},
        },
    )
    assert resp.status_code == 401  # no X-AI-Service-Secret header


def test_ai_callback_idempotency(client, db, citizen_token, ai_secret):
    ticket_id = _create_ticket(client, citizen_token)
    run_id = create_pending_ai_run(db, ticket_id)
    body = {
        "run_id": run_id,
        "ticket_id": ticket_id,
        "status": "succeeded",
        "recommendation": {"severity": "high", "confidence": 0.9},
    }

    resp1 = client.post(
        "/api/v1/ai/recommendations", headers={"X-AI-Service-Secret": ai_secret}, json=body
    )
    assert resp1.status_code == 200

    # Resend the identical callback for the same run_id.
    body["recommendation"]["severity"] = "low"  # even if the payload changed...
    resp2 = client.post(
        "/api/v1/ai/recommendations", headers={"X-AI-Service-Secret": ai_secret}, json=body
    )
    assert resp2.status_code == 200

    # ...the second call must be a no-op: the recommendation on file is still
    # the FIRST one (severity 'high'), proving run.status == 'succeeded'
    # short-circuited reprocessing rather than overwriting it.
    from app.models.ai import AiRecommendation

    rec = db.query(AiRecommendation).filter(AiRecommendation.ai_run_id == uuid.UUID(run_id)).one()
    assert rec.severity.value == "high"


def test_ai_callback_rejects_unknown_category_instead_of_nulling_it(
    client, db, citizen_token, ai_secret
):
    """Improvement 2: an AI recommendation with a category name that doesn't
    exist must be rejected (400), never silently stored as category_id=NULL."""
    ticket_id = _create_ticket(client, citizen_token)
    run_id = create_pending_ai_run(db, ticket_id)
    resp = client.post(
        "/api/v1/ai/recommendations",
        headers={"X-AI-Service-Secret": ai_secret},
        json={
            "run_id": run_id,
            "ticket_id": ticket_id,
            "status": "succeeded",
            "recommendation": {"category": "ThisCategoryDoesNotExist-xyz", "severity": "low"},
        },
    )
    assert resp.status_code == 400

    run = db.get(AiRun, uuid.UUID(run_id))
    db.refresh(run)
    # The run must NOT have been silently marked succeeded with a bad category.
    assert run.status == AiRunStatus.pending


def test_ai_evidence_type_mismatch_rejected_at_schema_level(client, db, citizen_token, ai_secret):
    ticket_id = _create_ticket(client, citizen_token)
    run_id = create_pending_ai_run(db, ticket_id)
    other_ticket_id = _create_ticket(client, citizen_token)
    resp = client.post(
        "/api/v1/ai/recommendations",
        headers={"X-AI-Service-Secret": ai_secret},
        json={
            "run_id": run_id,
            "ticket_id": ticket_id,
            "status": "succeeded",
            "recommendation": {"severity": "low"},
            "evidence": [
                {
                    "source_type": "SIMILAR_CASE",
                    "knowledge_chunk_id": str(uuid.uuid4()),
                    "cited_ticket_id": other_ticket_id,
                }
            ],
        },
    )
    assert resp.status_code == 422  # LEGAL/SIMILAR fields mismatched for the declared type


def test_similar_case_evidence_must_cite_completed_ticket(client, db, citizen_token, ai_secret):
    ticket_id = _create_ticket(client, citizen_token)
    run_id = create_pending_ai_run(db, ticket_id)
    not_completed_ticket_id = _create_ticket(client, citizen_token)  # still 'submitted'

    resp = client.post(
        "/api/v1/ai/recommendations",
        headers={"X-AI-Service-Secret": ai_secret},
        json={
            "run_id": run_id,
            "ticket_id": ticket_id,
            "status": "succeeded",
            "recommendation": {"severity": "low"},
            "evidence": [
                {"source_type": "SIMILAR_CASE", "cited_ticket_id": not_completed_ticket_id}
            ],
        },
    )
    assert (
        resp.status_code == 400
    )  # rejected: not_completed_ticket_id is 'submitted', not 'completed'


def test_similar_cases_endpoint_privacy_and_completed_only(client, db, citizen_token, ai_secret):
    """FIX 4: response must never include citizen_id/address/city, and must
    only ever contain completed tickets."""
    # Make a completed ticket directly (bypassing the full workflow -- what
    # matters here is only the read side: privacy + the status filter).
    resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers(citizen_token),
        json={
            "description": "Completed ticket for similar-cases privacy test",
            "lat": 30.3,
            "lng": 31.3,
            "address": "123 Secret Street",
            "city": "Nasr City",
        },
    )
    ticket_id = resp.json()["id"]
    ticket = db.get(Ticket, uuid.UUID(ticket_id))
    from app.models.enums import TicketStatus

    ticket.status = TicketStatus.completed
    db.commit()

    resp = client.get("/api/v1/ai/similar-cases", headers={"X-AI-Service-Secret": ai_secret})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) >= 1
    for item in results:
        assert item["status"] == "completed"
        for forbidden in ("citizen_id", "address", "city", "phone", "email"):
            assert forbidden not in item, f"{forbidden} must never appear in SimilarCaseOut"
        for allowed in (
            "ticket_id",
            "category_id",
            "description",
            "severity",
            "status",
            "governorate",
            "created_at",
            "completed_at",
        ):
            assert allowed in item


def test_similar_cases_requires_shared_secret(client):
    resp = client.get("/api/v1/ai/similar-cases")
    assert resp.status_code == 401


def test_legal_search_requires_shared_secret(client):
    resp = client.post("/api/v1/ai/legal-search", json={"query_embedding": [0.1, 0.2, 0.3, 0.4]})
    assert resp.status_code == 401


def test_legal_search_finds_matching_chunk_via_pgvector(client, db, ai_secret):
    """FIX 3 + pgvector check: insert a legal chunk with a small test
    embedding, then confirm a near-identical query vector retrieves it via
    real cosine-distance search against Postgres/pgvector -- not a mock."""
    doc = LegalKnowledgeDocument(
        title=f"Pytest Legal Doc {uuid.uuid4().hex[:8]}",
        source_type="regulation",
        content="Potholes must be repaired within 72 hours.",
    )
    db.add(doc)
    db.flush()
    chunk = LegalKnowledgeChunk(
        document_id=doc.id,
        chunk_index=0,
        content="Potholes must be repaired within 72 hours.",
        embedding=[1.0, 0.0, 0.0, 0.0],
        embedding_dim=4,
    )
    db.add(chunk)
    db.commit()

    resp = client.post(
        "/api/v1/ai/legal-search",
        headers={"X-AI-Service-Secret": ai_secret},
        json={"query_embedding": [0.9, 0.1, 0.0, 0.0], "limit": 5},
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()
    chunk_ids = {r["chunk_id"] for r in results}
    assert str(chunk.id) in chunk_ids
    match = next(r for r in results if r["chunk_id"] == str(chunk.id))
    assert match["similarity_score"] > 0.8  # near-identical vectors -> high similarity
    assert "content" in match and "title" in match


def test_legal_search_never_touches_tickets(client, ai_secret):
    """Sanity check on the contract itself: the response schema has no field
    that could carry ticket/citizen data."""
    resp = client.post(
        "/api/v1/ai/legal-search",
        headers={"X-AI-Service-Secret": ai_secret},
        json={"query_embedding": [0.1, 0.2, 0.3, 0.4]},
    )
    assert resp.status_code == 200
    for item in resp.json():
        for forbidden in ("ticket_id", "citizen_id", "cited_ticket_id"):
            assert forbidden not in item

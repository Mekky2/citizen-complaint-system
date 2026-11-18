"""End-to-end API tests through FastAPI's TestClient (offline runtime, no keys).

These tests exercise the same wiring the frontend uses: one ``/api/v1/chat`` endpoint routes to
either the Complaint Agent or the RAG Agent, tickets start as ``Pending``, and a ticket is
only created after explicit citizen confirmation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.runtime import reset_runtime


@pytest.fixture()
def client():
    reset_runtime()
    with TestClient(create_app()) as test_client:
        yield test_client
    reset_runtime()


def _chat(client: TestClient, message: str, session_id: str = "e2e") -> dict:
    response = client.post(
        "/api/v1/chat", json={"message": message, "session_id": session_id}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health_and_knowledge_status(client):
    assert client.get("/health").json()["status"] == "ok"

    status = client.get("/api/v1/knowledge/status").json()
    assert status["documents"] == 15
    assert status["chunks"] > 100
    assert status["embedding_provider"] == "hashing"
    assert status["embedding_dimension"] == 1024


def test_complaint_creates_pending_ticket_only_after_confirmation(client):
    first = _chat(
        client,
        "ماسورة مياه مكسورة في شارع النيل بالجيزة من يومين",
        session_id="e2e-complaint",
    )
    assert first["type"] == "complaint"
    assert first["requires_confirmation"] is True
    assert first["stage"] == "awaiting_confirmation"
    assert first["ticket"] is None
    assert client.get("/api/v1/tickets").json() == []

    confirmed = _chat(client, "نعم أكد الإرسال", session_id="e2e-complaint")
    ticket = confirmed["ticket"]
    assert confirmed["stage"] == "submitted"
    assert ticket["status"] == "Pending"
    assert ticket["ticket_id"].startswith("TKT-")

    listed = client.get("/api/v1/tickets").json()
    assert [item["ticket_id"] for item in listed] == [ticket["ticket_id"]]

    fetched = client.get(f"/api/v1/tickets/{ticket['ticket_id']}").json()
    assert fetched["ticket_id"] == ticket["ticket_id"]


def test_question_returns_cited_arabic_answer(client):
    result = _chat(client, "كيف أقدم شكوى؟", session_id="e2e-rag")

    assert result["type"] == "rag"
    assert result["found_in_kb"] is True
    assert result["sources"], "an answer must cite at least one knowledge-base document"
    assert "المصدر:" in result["reply_ar"]
    assert any("\u0600" <= char <= "\u06ff" for char in result["reply_ar"])


def test_review_endpoint_updates_status_and_adds_note(client):
    _chat(client, "زبالة متراكمة في شارع النيل", session_id="e2e-review")
    confirmed = _chat(client, "نعم", session_id="e2e-review")
    ticket_id = confirmed["ticket"]["ticket_id"]

    response = client.post(
        f"/api/v1/tickets/{ticket_id}/review",
        json={"status": "Approved", "reviewer_note": "تم التحقق من الموقع"},
    )
    assert response.status_code == 200
    reviewed = response.json()
    assert reviewed["status"] == "Approved"
    # Reviewer notes stay internal on purpose; the citizen-facing payload must not leak them.
    assert "review_notes" not in reviewed


def _new_ticket(client: TestClient, session_id: str, text: str) -> str:
    _chat(client, text, session_id=session_id)
    confirmed = _chat(client, "نعم", session_id=session_id)
    return confirmed["ticket"]["ticket_id"]


def test_ticket_lifecycle_follows_documented_transitions(client):
    ticket_id = _new_ticket(
        client, "e2e-lifecycle", "ماسورة مياه مكسورة في شارع الجمهورية"
    )

    for status in ["Approved", "In Progress", "Verifying", "Done"]:
        response = client.post(
            f"/api/v1/tickets/{ticket_id}/review", json={"status": status}
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    final = client.get(f"/api/v1/tickets/{ticket_id}").json()
    assert final["status"] == "Done"


def test_invalid_transition_is_rejected_without_changing_status(client):
    ticket_id = _new_ticket(
        client, "e2e-transition", "إنارة الشارع مقطوعة في شارع النيل"
    )

    response = client.post(
        f"/api/v1/tickets/{ticket_id}/review", json={"status": "Done"}
    )

    assert response.status_code == 409
    assert "انتقال حالة غير مسموح" in response.json()["detail"]
    assert client.get(f"/api/v1/tickets/{ticket_id}").json()["status"] == "Pending"


def test_dismissed_and_declined_statuses_are_supported(client):
    dismissed = _new_ticket(
        client, "e2e-dismiss", "شكوى مكررة عن القمامة في شارع النيل"
    )
    assert (
        client.post(
            f"/api/v1/tickets/{dismissed}/review", json={"status": "Dismissed"}
        ).json()["status"]
        == "Dismissed"
    )

    declined = _new_ticket(
        client, "e2e-decline", "حفرة في شارع النيل"
    )
    assert (
        client.post(
            f"/api/v1/tickets/{declined}/review", json={"status": "Declined"}
        ).json()["status"]
        == "Declined"
    )


def test_review_unknown_ticket_returns_404(client):
    assert client.get("/api/v1/tickets/TKT-0000-0000").status_code == 404
    assert (
        client.post(
            "/api/v1/tickets/TKT-0000-0000/review", json={"status": "Approved"}
        ).status_code
        == 404
    )


def test_validation_errors_do_not_echo_the_message(client):
    response = client.post(
        "/api/v1/chat", json={"message": "x" * 5000, "session_id": "too-long"}
    )
    assert response.status_code == 422
    assert "x" * 100 not in response.text
    assert response.json()["detail"][0]["type"] == "string_too_long"

    missing = client.post("/api/v1/chat", json={})
    assert missing.status_code == 422
    assert missing.json()["detail"][0]["type"] == "missing"


def test_unanswerable_question_does_not_invent_information(client):
    result = _chat(client, "كم رسوم استخراج رخصة القيادة؟", session_id="e2e-unknown")

    assert result["type"] == "rag"
    assert result["found_in_kb"] is False
    assert "المعلومات غير متوفرة" in result["reply_ar"]
    assert result["sources"] == []


def test_emergency_message_uses_official_numbers_and_creates_no_ticket(client):
    result = _chat(client, "فيه حريق في الشارع", session_id="e2e-emergency")

    assert result["type"] in {"complaint", "rag"}
    assert "180" in result["reply_ar"]
    assert client.get("/api/v1/tickets").json() == []

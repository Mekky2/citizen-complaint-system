"""Tickets: citizen creation, access control (IDOR check), supervisor access, status transitions."""

from tests.conftest import auth_headers


def _create_ticket(client, token):
    resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers(token),
        json={"description": "Pytest pothole report on a test street", "lat": 30.0, "lng": 31.0},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_citizen_creates_ticket(client, citizen_token):
    ticket = _create_ticket(client, citizen_token)
    assert ticket["status"] == "submitted"
    assert ticket["citizen_id"] is not None


def test_citizen_can_only_access_own_ticket(client, citizen_token, citizen_token_factory):
    ticket = _create_ticket(client, citizen_token)
    other_token, _ = citizen_token_factory()

    # Owner can read it.
    resp = client.get(f"/api/v1/tickets/{ticket['id']}", headers=auth_headers(citizen_token))
    assert resp.status_code == 200

    # A different citizen (IDOR check) cannot, even with a syntactically valid ticket_id.
    resp = client.get(f"/api/v1/tickets/{ticket['id']}", headers=auth_headers(other_token))
    assert resp.status_code == 403


def test_citizen_list_only_shows_own_tickets(client, citizen_token_factory):
    token_a, _ = citizen_token_factory()
    token_b, _ = citizen_token_factory()
    ticket_a = _create_ticket(client, token_a)

    resp = client.get("/api/v1/tickets", headers=auth_headers(token_b))
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert ticket_a["id"] not in ids


def test_supervisor_can_access_any_ticket(client, citizen_token, supervisor_token):
    ticket = _create_ticket(client, citizen_token)
    resp = client.get(f"/api/v1/tickets/{ticket['id']}", headers=auth_headers(supervisor_token))
    assert resp.status_code == 200


def test_status_transition_trigger_ai_run_moves_ticket_to_under_ai_review(
    client, citizen_token, supervisor_token
):
    ticket = _create_ticket(client, citizen_token)
    resp = client.post(
        f"/api/v1/ai/tickets/{ticket['id']}/trigger", headers=auth_headers(supervisor_token)
    )
    assert resp.status_code == 201, resp.text
    # No AI service is listening in this test environment, so the trigger call
    # itself fails and the run is recorded 'failed' -- but the important,
    # testable fact is the STATUS TRANSITION already happened before that
    # network call, and is not rolled back by the AI service being down.
    assert resp.json()["status"] in ("failed", "succeeded")

    resp = client.get(f"/api/v1/tickets/{ticket['id']}", headers=auth_headers(supervisor_token))
    assert resp.json()["status"] == "under_ai_review"


def test_citizen_cannot_create_ticket_on_behalf_of_admin_role_only_self(client, admin_token):
    # 'citizen' role is required to create a ticket; an admin is not a citizen.
    resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers(admin_token),
        json={
            "description": "Admin should not be able to do this directly",
            "lat": 30.0,
            "lng": 31.0,
        },
    )
    assert resp.status_code == 403

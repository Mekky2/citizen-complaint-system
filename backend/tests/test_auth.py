"""Authentication: registration, login, invalid credentials, JWT validation, role authorization."""
from tests.conftest import auth_headers, unique, unique_digits


def test_register_and_login(client):
    phone = f"010{unique_digits(8)}"
    resp = client.post("/api/v1/auth/register", json={"name": "Reg Test", "phone": phone, "password": "password123"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body

    resp = client.post("/api/v1/auth/login", json={"identifier": phone, "password": "password123"})
    assert resp.status_code == 200, resp.text
    assert "access_token" in resp.json()


def test_login_invalid_credentials(client):
    resp = client.post("/api/v1/auth/login", json={"identifier": "nobody@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_register_duplicate_phone_conflicts(client):
    phone = f"011{unique_digits(8)}"
    # CitizenRegisterIn.name requires min_length=3 — "A"/"B" alone 422 before
    # the duplicate-phone check is ever reached, which is what this test means
    # to exercise.
    resp1 = client.post("/api/v1/auth/register", json={"name": "Person A", "phone": phone, "password": "password123"})
    assert resp1.status_code == 201, resp1.text
    resp2 = client.post("/api/v1/auth/register", json={"name": "Person B", "phone": phone, "password": "password123"})
    assert resp2.status_code == 409, resp2.text


def test_jwt_rejected_when_malformed(client):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_no_token_rejected(client):
    resp = client.get("/api/v1/tickets")
    assert resp.status_code == 401


def test_me_returns_correct_identity(client, citizen_token):
    resp = client.get("/api/v1/auth/me", headers=auth_headers(citizen_token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "citizen"


def test_role_authorization_citizen_cannot_create_staff(client, citizen_token):
    resp = client.post(
        "/api/v1/admin/staff",
        headers=auth_headers(citizen_token),
        json={"name": "x", "email": f"{unique()}@example.com", "password": "password123", "role": "admin"},
    )
    assert resp.status_code == 403


def test_role_authorization_admin_can_create_staff(client, admin_token):
    resp = client.post(
        "/api/v1/admin/staff",
        headers=auth_headers(admin_token),
        json={"name": "Staff", "email": f"{unique()}@example.com", "password": "password123", "role": "supervisor"},
    )
    assert resp.status_code == 201

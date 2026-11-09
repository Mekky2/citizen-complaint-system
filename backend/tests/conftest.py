"""
Shared fixtures for the integration test suite.

These tests run against the REAL, already-deployed egcivic Postgres database
(DATABASE_URL in .env) through FastAPI's TestClient — not a mocked session,
not an in-memory/sqlite substitute. That is deliberate: the whole point of
this project's backend is "maps onto a real, pre-existing database", so the
tests exercise exactly that, the same way the manual curl pass during
initial development did. There is no teardown/rollback-per-test — each test
uses a random suffix (see `unique()`) so repeated runs don't collide with
data from previous runs, and test data is left in place afterwards (noted
as a limitation in the final delivery write-up).

A bootstrap admin is created once per test session, directly via the ORM
(bypassing the API, since there is intentionally no API path that creates
the first admin — see README "First admin account").
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import SessionLocal
from app.main import app
from app.models.ai import AiRun
from app.models.enums import AiRunStatus
from app.models.identity import Role, User, UserRole
from app.security.hashing import hash_password


def unique() -> str:
    return uuid.uuid4().hex[:10]


def unique_digits(n: int = 8) -> str:
    """
    Digits only, unlike unique() (hex — can contain a-f). Needed anywhere a
    value has to satisfy PHONE_RE (^01[0125][0-9]{8}$) — both a Pydantic
    validator (app/schemas/auth.py) AND the database's own
    users_phone_format_check CHECK constraint reject a non-digit phone
    suffix, so a test phone built from hex (as this fixture file used to)
    fails BEFORE the test's own assertions ever run, with a confusing
    cascade of unrelated-looking fixture errors. uuid4().int is a large
    integer; str() of it is decimal digits only, so slicing it can never
    produce a letter.
    """
    return str(uuid.uuid4().int)[:n]


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def db():
    session = SessionLocal()
    yield session
    session.close()


def _create_user_with_role(db, *, name: str, email: str, phone: str, password: str, role_name: str) -> uuid.UUID:
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role is not None, f"role '{role_name}' is not seeded — check database/init/06_seed.sql"
    user = User(name=name, email=email, phone=phone, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user.id


def login(client: TestClient, identifier: str, password: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_token(client: TestClient, db) -> str:
    suffix = unique()
    email = f"admin.{suffix}@example.com"
    phone = f"010{unique_digits(8)}"
    password = "AdminPass123"
    _create_user_with_role(db, name="Test Admin", email=email, phone=phone, password=password, role_name="admin")
    return login(client, email, password)


@pytest.fixture(scope="session")
def supervisor_token(client: TestClient, admin_token: str) -> str:
    suffix = unique()
    email = f"sup.{suffix}@example.com"
    resp = client.post(
        "/api/v1/admin/staff",
        headers=auth_headers(admin_token),
        json={"name": "Test Supervisor", "email": email, "phone": f"011{unique_digits(8)}",
              "password": "SupPass123", "role": "supervisor"},
    )
    assert resp.status_code == 201, resp.text
    return login(client, email, "SupPass123")


@pytest.fixture(scope="session")
def citizen_token_factory(client: TestClient):
    def _make() -> tuple[str, str]:
        suffix = unique()
        phone = f"012{unique_digits(8)}"
        resp = client.post(
            "/api/v1/auth/register",
            json={"name": "Test Citizen", "phone": phone, "password": "password123"},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["access_token"], phone

    return _make


@pytest.fixture(scope="session")
def citizen_token(citizen_token_factory) -> str:
    token, _phone = citizen_token_factory()
    return token


@pytest.fixture(scope="session")
def department_id(client: TestClient, admin_token: str) -> str:
    resp = client.post(
        "/api/v1/admin/departments",
        headers=auth_headers(admin_token),
        json={"name": f"Test Dept {unique()}", "description": "pytest fixture department"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture(scope="session")
def category_id(client: TestClient, admin_token: str, department_id: str) -> str:
    resp = client.post(
        "/api/v1/admin/categories",
        headers=auth_headers(admin_token),
        json={"name": f"Test Category {unique()}", "default_department_id": department_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def make_technician(client: TestClient, admin_token: str) -> tuple[str, str, str]:
    """Returns (user_id, email, access_token) for a brand-new technician account."""
    suffix = unique()
    email = f"tech.{suffix}@example.com"
    resp = client.post(
        "/api/v1/admin/staff",
        headers=auth_headers(admin_token),
        json={"name": "Test Technician", "email": email, "phone": f"015{unique_digits(8)}",
              "password": "TechPass123", "role": "technician"},
    )
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["id"]
    token = login(client, email, "TechPass123")
    return user_id, email, token


def make_team(client: TestClient, admin_token: str, department_id: str) -> str:
    resp = client.post(
        "/api/v1/maintenance/teams",
        headers=auth_headers(admin_token),
        json={"department_id": department_id, "name": f"Test Team {unique()}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture(scope="session")
def ai_secret() -> str:
    return get_settings().ai_service_shared_secret


def create_pending_ai_run(db, ticket_id: str) -> str:
    """
    Simulates "the AI service accepted the trigger and is working on it" by
    inserting an ai_runs row directly (status='pending'), the same state
    app/services/ai.py:trigger_ai_run() leaves behind right after a
    SUCCESSFUL POST to the AI service. Used so tests can then call
    POST /api/v1/ai/recommendations against a real, valid run_id without
    needing an actual AI service listening in the test environment.
    """
    run = AiRun(ticket_id=uuid.UUID(ticket_id), status=AiRunStatus.pending)
    db.add(run)
    db.commit()
    db.refresh(run)
    return str(run.id)


def approve_ticket_to_assigned(client: TestClient, db, *, ticket_id: str, supervisor_token: str, ai_secret: str) -> None:
    """Drives a freshly 'under_ai_review' ticket through a successful AI
    callback and a supervisor approval, landing it at status='assigned' —
    the precondition for creating a maintenance task."""
    run_id = create_pending_ai_run(db, ticket_id)
    resp = client.post(
        "/api/v1/ai/recommendations",
        headers={"X-AI-Service-Secret": ai_secret},
        json={
            "run_id": run_id, "ticket_id": ticket_id, "status": "succeeded",
            "recommendation": {"severity": "medium", "confidence": 0.8, "explanation": "pytest-seeded"},
        },
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        f"/api/v1/supervisor/tickets/{ticket_id}/decisions",
        headers=auth_headers(supervisor_token),
        json={"action": "approve"},
    )
    assert resp.status_code == 201, resp.text


def create_assigned_ticket(client: TestClient, db, *, citizen_token: str, supervisor_token: str, ai_secret: str) -> str:
    """Full pipeline: citizen creates a ticket -> supervisor triggers AI review
    -> (simulated) AI recommendation -> supervisor approves. Returns a
    ticket_id sitting at status='assigned', ready for a maintenance task."""
    resp = client.post(
        "/api/v1/tickets",
        headers=auth_headers(citizen_token),
        json={"description": "Pytest-seeded ticket for the maintenance pipeline", "lat": 30.1, "lng": 31.1},
    )
    assert resp.status_code == 201, resp.text
    ticket_id = resp.json()["id"]

    resp = client.post(f"/api/v1/ai/tickets/{ticket_id}/trigger", headers=auth_headers(supervisor_token))
    assert resp.status_code == 201, resp.text

    approve_ticket_to_assigned(client, db, ticket_id=ticket_id, supervisor_token=supervisor_token, ai_secret=ai_secret)
    return ticket_id

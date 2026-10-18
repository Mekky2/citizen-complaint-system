from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_health_ok():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_default_tool_limits_match_architecture():
    s = get_settings()
    assert s.tool_call_limit_per_ticket == 8
    assert s.tool_call_limit_per_tool == 3

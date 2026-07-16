import pytest
import time
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    settings = Settings(
        environment="test",
        mcp_transport="in-process",
        a2a_transport="in-process",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _plan_payload():
    return {
        "destination": "北京",
        "start_date": "2025-08-11",
        "days": 2,
        "budget_level": "mid",
        "interests": ["历史文化"],
        "hotel_type": "舒适型",
    }


def test_plan_returns_task_id(client):
    resp = client.post("/api/v1/plan", json=_plan_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"]
    assert body["status"] == "accepted"
    assert resp.headers["X-Request-Id"]


def test_plan_missing_destination_rejected(client):
    payload = _plan_payload()
    payload["destination"] = ""
    resp = client.post("/api/v1/plan", json=payload)
    assert resp.status_code == 422


def test_plan_result_available(client):
    resp = client.post("/api/v1/plan", json=_plan_payload())
    task_id = resp.json()["task_id"]
    for _ in range(30):
        time.sleep(0.5)
        result = client.get(f"/api/v1/plan/{task_id}")
        if result.status_code == 200:
            data = result.json()
            if data.get("status") in ("success", "partial"):
                assert "itinerary" in data
                return
    raise AssertionError("行程未在预期时间内完成")


def test_plan_result_not_found(client):
    resp = client.get("/api/v1/plan/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "E_NOT_FOUND"


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"]["alive"] is True
    assert body["dependencies"][0]["available"] is True


def test_index_page_served(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_metrics_endpoint(client):
    client.post("/api/v1/plan", json=_plan_payload())
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "by_type" in resp.json()


def test_rate_limiting():
    settings = Settings(
        rate_limit_per_minute=2,
        environment="test",
        mcp_transport="in-process",
        a2a_transport="in-process",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        r1 = c.post("/api/v1/plan", json=_plan_payload())
        r2 = c.post("/api/v1/plan", json=_plan_payload())
        r3 = c.post("/api/v1/plan", json=_plan_payload())
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["error"]["code"] == "E_RATE_LIMITED"

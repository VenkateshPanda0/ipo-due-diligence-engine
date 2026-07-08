from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["rules_count"] == 16
    assert body["ruleset_version"] == "1.0.0"


def test_readiness_reports_unconfirmed_production_gate() -> None:
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_attention"
    assert body["production_ready"] is False
    assert body["checks"]["rules_loaded"] is True
    assert body["checks"]["regulatory_validation_confirmed"] is False

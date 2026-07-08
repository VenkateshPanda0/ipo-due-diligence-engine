from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_rules_list_and_category_filter() -> None:
    client = TestClient(app)

    all_rules = client.get("/rules")
    mandatory = client.get("/rules?category=mandatory")
    advisory = client.get("/rules?category=advisory")

    assert all_rules.status_code == 200
    assert all_rules.json()["total_count"] == 16
    assert mandatory.json()["total_count"] == 11
    assert advisory.json()["total_count"] == 5


def test_rule_detail_and_unknown_rule() -> None:
    client = TestClient(app)

    detail = client.get("/rules/NTA_3CR")
    missing = client.get("/rules/UNKNOWN")

    assert detail.status_code == 200
    assert detail.json()["rule_id"] == "NTA_3CR"
    assert detail.json()["category"] == "mandatory"
    assert missing.status_code == 404

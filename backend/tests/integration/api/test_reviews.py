from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures.company_data_factory import CompanyDataFactory


def _create_report(client: TestClient) -> str:
    response = client.post(
        "/screen/json",
        json=CompanyDataFactory.create().model_dump(mode="json"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["machine_assessment_only"] is True
    assert body["human_review_required"] is True
    assert body["decision_authority"] == "human_reviewer"
    return str(body["report_id"])


def test_human_review_can_be_opened_and_completed() -> None:
    client = TestClient(app)
    report_id = _create_report(client)

    open_response = client.post(f"/reviews/reports/{report_id}")

    assert open_response.status_code == 200
    opened = open_response.json()
    assert opened["report_id"] == report_id
    assert opened["machine_status"] == "eligible"
    assert opened["status"] == "pending"
    assert opened["final_decision"] is None

    decision_response = client.post(
        f"/reviews/{opened['review_id']}/decision",
        json={
            "reviewer_name": "Lead Analyst",
            "final_decision": "proceed",
            "rationale": "Mandatory checks pass and advisory items are acceptable.",
            "conditions": ["Verify latest SEBI circulars before engagement letter."],
        },
    )

    assert decision_response.status_code == 200
    completed = decision_response.json()
    assert completed["status"] == "completed"
    assert completed["final_decision"] == "proceed"
    assert completed["reviewer_name"] == "Lead Analyst"
    assert completed["completed_at"] is not None


def test_open_review_is_idempotent_for_same_report() -> None:
    client = TestClient(app)
    report_id = _create_report(client)

    first = client.post(f"/reviews/reports/{report_id}")
    second = client.post(f"/reviews/reports/{report_id}")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["review_id"] == second.json()["review_id"]


def test_open_review_unknown_report_returns_404() -> None:
    client = TestClient(app)

    response = client.post(f"/reviews/reports/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REPORT_NOT_FOUND"


def test_self_declared_role_header_is_ignored(app_factory) -> None:  # type: ignore[no-untyped-def]
    """Regression (D11): X-User-Role must not grant reviewer rights."""
    client = app_factory(API_KEYS="ana|analyst|ana-key,rev|reviewer|rev-key")
    analyst = {"Authorization": "Bearer ana-key"}
    report = client.post(
        "/screen/json", json=CompanyDataFactory.create().model_dump(mode="json"), headers=analyst
    )
    assert report.status_code == 200
    review = client.post(f"/reviews/reports/{report.json()['report_id']}", headers=analyst)
    decision = {
        "reviewer_name": "Lead Analyst",
        "final_decision": "proceed",
        "rationale": "Reviewed.",
        "conditions": [],
    }

    spoofed = client.post(
        f"/reviews/{review.json()['review_id']}/decision",
        json=decision,
        headers={**analyst, "X-User-Role": "reviewer"},
    )
    assert spoofed.status_code == 403

    legit = client.post(
        f"/reviews/{review.json()['review_id']}/decision",
        json=decision,
        headers={"Authorization": "Bearer rev-key"},
    )
    assert legit.status_code == 200

    again = client.post(
        f"/reviews/{review.json()['review_id']}/decision",
        json=decision,
        headers={"Authorization": "Bearer rev-key"},
    )
    assert again.status_code == 409  # decisions are immutable


def test_legacy_api_key_maps_to_analyst(app_factory) -> None:  # type: ignore[no-untyped-def]
    client = app_factory(API_KEY="secret")
    assert (
        client.get("/api/v1/me", headers={"Authorization": "Bearer secret"}).json()["role"]
        == "analyst"
    )
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers={"Authorization": "Bearer wrong"}).status_code == 401

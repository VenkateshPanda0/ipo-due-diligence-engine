from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
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


def test_complete_review_requires_reviewer_role_when_api_key_configured() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(API_KEY="secret")
    client = TestClient(app)
    report_response = client.post(
        "/screen/json",
        json=CompanyDataFactory.create().model_dump(mode="json"),
        headers={"Authorization": "Bearer secret"},
    )
    review_response = client.post(
        f"/reviews/reports/{report_response.json()['report_id']}",
        headers={"Authorization": "Bearer secret"},
    )

    missing_role = client.post(
        f"/reviews/{review_response.json()['review_id']}/decision",
        json={
            "reviewer_name": "Lead Analyst",
            "final_decision": "proceed",
            "rationale": "Reviewed.",
            "conditions": [],
        },
        headers={"Authorization": "Bearer secret"},
    )
    valid_role = client.post(
        f"/reviews/{review_response.json()['review_id']}/decision",
        json={
            "reviewer_name": "Lead Analyst",
            "final_decision": "proceed",
            "rationale": "Reviewed.",
            "conditions": [],
        },
        headers={"Authorization": "Bearer secret", "X-User-Role": "reviewer"},
    )
    app.dependency_overrides.clear()

    assert missing_role.status_code == 403
    assert valid_role.status_code == 200

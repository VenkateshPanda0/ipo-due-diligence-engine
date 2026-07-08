from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.constants import MAX_UPLOAD_SIZE_BYTES
from app.main import app
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_screen_json_accepts_raw_company_data() -> None:
    client = TestClient(app)
    payload = CompanyDataFactory.create().model_dump(mode="json")

    response = client.post("/screen/json", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "eligible"
    assert body["mandatory_progress"]["total_rules"] == 11
    assert len(body["mandatory_results"]) == 11
    assert body["ruleset_version"] == "1.0.0"
    assert response.headers["X-Request-ID"]


def test_screen_json_accepts_wrapped_company_data() -> None:
    client = TestClient(app)
    payload = {"company_data": CompanyDataFactory.create_not_eligible().model_dump(mode="json")}

    response = client.post("/screen/json", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "not_eligible"


def test_screen_json_validation_error_uses_error_envelope() -> None:
    client = TestClient(app)

    response = client.post("/screen/json", json={"company_data": {"bad": "payload"}})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_screen_json_requires_api_key_when_configured() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(API_KEY="secret")
    client = TestClient(app)
    payload = CompanyDataFactory.create().model_dump(mode="json")

    missing_key_response = client.post("/screen/json", json=payload)
    valid_key_response = client.post(
        "/screen/json",
        json=payload,
        headers={"Authorization": "Bearer secret"},
    )

    app.dependency_overrides.clear()

    assert missing_key_response.status_code == 401
    assert valid_key_response.status_code == 200


def test_screen_pdf_extracts_embedded_company_data() -> None:
    client = TestClient(app)
    company_json = json.dumps(CompanyDataFactory.create().model_dump(mode="json"))
    content = (
        "Draft Red Herring Prospectus\n"
        "BEGIN_COMPANY_DATA_JSON\n"
        f"{company_json}\n"
        "END_COMPANY_DATA_JSON"
    ).encode()

    response = client.post(
        "/screen/pdf",
        files={"file": ("sample.pdf", content, "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "eligible"


def test_screen_pdf_unknown_document_returns_error_envelope() -> None:
    client = TestClient(app)

    response = client.post(
        "/screen/pdf",
        files={"file": ("sample.pdf", b"unrecognized content", "application/pdf")},
    )

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "UNSUPPORTED_DOCUMENT"


def test_screen_pdf_rejects_non_pdf_upload() -> None:
    client = TestClient(app)

    response = client.post(
        "/screen/pdf",
        files={"file": ("sample.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 415


def test_screen_pdf_rejects_oversized_upload() -> None:
    client = TestClient(app)

    response = client.post(
        "/screen/pdf",
        files={"file": ("sample.pdf", b"x" * (MAX_UPLOAD_SIZE_BYTES + 1), "application/pdf")},
    )

    assert response.status_code == 413

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_screen_json_accepts_raw_company_data() -> None:
    client = TestClient(app)
    payload = CompanyDataFactory.create().model_dump(mode="json")

    response = client.post("/screen/json", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "eligible"
    assert body["mandatory_progress"]["total_rules"] == 13
    assert len(body["mandatory_results"]) == 13
    assert body["ruleset_version"] == "2.0.0"
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


def test_screen_json_requires_api_key_when_configured(app_factory) -> None:  # type: ignore[no-untyped-def]
    client = app_factory(API_KEY="secret")
    payload = CompanyDataFactory.create().model_dump(mode="json")
    missing_key_response = client.post("/screen/json", json=payload)
    valid_key_response = client.post(
        "/screen/json", json=payload, headers={"Authorization": "Bearer secret"}
    )

    assert missing_key_response.status_code == 401
    assert valid_key_response.status_code == 200


def test_screen_pdf_ignores_embedded_company_data() -> None:
    """Regression (D8): text inside a real PDF cannot dictate its own screening outcome."""
    from tests.fixtures.pdf_factory import DocSpec, PageSpec, build_pdf

    company_json = json.dumps(CompanyDataFactory.create().model_dump(mode="json"))
    chunks = [company_json[i : i + 90] for i in range(0, len(company_json), 90)][:40]
    pdf = build_pdf(
        DocSpec(
            [
                PageSpec(
                    lines=[
                        "DRAFT RED HERRING PROSPECTUS",
                        "BEGIN_COMPANY_DATA_JSON",
                        *chunks,
                        "END_COMPANY_DATA_JSON",
                    ]
                )
            ]
        )
    )
    response = TestClient(app).post(
        "/screen/pdf", files={"file": ("sample.pdf", pdf, "application/pdf")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] != "eligible"
    assert body["outcome"] == "insufficient_evidence"


def test_screen_pdf_unrecognised_pdf_returns_unsupported_document() -> None:
    from tests.fixtures.pdf_factory import DocSpec, PageSpec, build_pdf

    pdf = build_pdf(DocSpec([PageSpec(lines=["A shopping list", "eggs", "milk"])]))
    response = TestClient(app).post(
        "/screen/pdf", files={"file": ("list.pdf", pdf, "application/pdf")}
    )

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "UNSUPPORTED_DOCUMENT"


def test_screen_pdf_rejects_non_pdf_bytes_even_with_pdf_content_type() -> None:
    response = TestClient(app).post(
        "/screen/pdf", files={"file": ("sample.pdf", b"unrecognized content", "application/pdf")}
    )
    assert response.status_code == 415
    assert response.json()["error"]["details"]["reason"] == "not_pdf"


def test_screen_pdf_rejects_non_pdf_upload() -> None:
    response = TestClient(app).post(
        "/screen/pdf", files={"file": ("sample.txt", b"plain text", "text/plain")}
    )
    assert response.status_code == 415


def test_screen_pdf_rejects_oversized_upload() -> None:
    from app.core.config import get_settings

    limit = get_settings().max_upload_size_bytes
    response = TestClient(app).post(
        "/screen/pdf",
        files={"file": ("sample.pdf", b"%PDF-1.4\n" + b"x" * limit, "application/pdf")},
    )
    assert response.status_code == 413

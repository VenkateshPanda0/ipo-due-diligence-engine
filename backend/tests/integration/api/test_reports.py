from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures.company_data_factory import CompanyDataFactory


def test_report_retrieval_all_formats() -> None:
    client = TestClient(app)
    screen_response = client.post(
        "/screen/json",
        json=CompanyDataFactory.create().model_dump(mode="json"),
    )
    report_id = screen_response.json()["report_id"]

    json_response = client.get(f"/reports/{report_id}?format=json")
    html_response = client.get(f"/reports/{report_id}?format=html")
    text_response = client.get(f"/reports/{report_id}?format=text")

    assert json_response.status_code == 200
    assert json_response.json()["report_id"] == report_id
    assert html_response.status_code == 200
    assert "text/html" in html_response.headers["content-type"]
    assert "<!doctype html>" in html_response.text
    assert text_response.status_code == 200
    assert "IPO Due Diligence Report" in text_response.text


def test_report_retrieval_unknown_id_returns_404() -> None:
    client = TestClient(app)

    response = client.get(f"/reports/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REPORT_NOT_FOUND"

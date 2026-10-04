"""End-to-end API v1 workflow tests (synthetic PDFs, inline processing)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.fixtures.pdf_factory import standard_drhp

ADMIN = {"Authorization": "Bearer admin-key"}
ANALYST = {"Authorization": "Bearer ana-key"}
REVIEWER = {"Authorization": "Bearer rev-key"}
VIEWER = {"Authorization": "Bearer view-key"}
KEYS = "boss|admin|admin-key,ana|analyst|ana-key,rev|reviewer|rev-key,vic|viewer|view-key"


def _client(app_factory: Any, **kw: Any) -> TestClient:
    return app_factory(API_KEYS=KEYS, **kw)


def _case(client: TestClient, name: str = "Acme Industries Limited") -> dict[str, Any]:
    r = client.post("/api/v1/cases", json={"company_name": name}, headers=ANALYST)
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client: TestClient, case_id: str, pdf: bytes, name: str = "drhp.pdf") -> dict[str, Any]:
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": (name, pdf, "application/pdf")},
        headers=ANALYST,
    )
    assert r.status_code == 202, r.text
    return r.json()


def test_full_case_workflow(app_factory: Any) -> None:
    client = _client(app_factory)
    case = _case(client)
    assert case["status"] == "draft" and case["current_version"] == 1

    doc = _upload(client, case["id"], standard_drhp())
    doc = client.get(f"/api/v1/documents/{doc['id']}", headers=VIEWER).json()
    assert doc["status"] == "awaiting_review"  # narrative declarations need verification
    assert doc["doc_type"] == "drhp" and doc["page_count"] == 3 and len(doc["sha256"]) == 64

    extraction = client.get(f"/api/v1/documents/{doc['id']}/extraction", headers=VIEWER).json()
    by_path = {f["field_path"]: f for f in extraction["fields"]}
    nta = by_path["financials.fiscal_years[FY2024].net_tangible_assets"]
    assert nta["status"] == "extracted_high_confidence"
    assert nta["selected"]["value"] == "123.4567"
    assert (
        nta["selected"]["original_text"] == "12,345.67"
        and nta["selected"]["original_unit"] == "INR_LAKH"
    )
    assert nta["selected"]["page_number"] == 2
    assert extraction["run"]["environment"]["pipeline_version"]

    data = client.get(f"/api/v1/cases/{case['id']}/data", headers=VIEWER).json()
    assert data["version"] == 2 and data["source"] == "extraction"
    assert (
        data["payload"]["issue_details"]["issue_type"] == "mixed"
    )  # suggestion applied when unset

    items = client.get(
        "/api/v1/review-items", params={"case_id": case["id"]}, headers=VIEWER
    ).json()
    paths = {i["field_path"] for i in items}
    assert "declarations.debarred_by_sebi" in paths
    assert (
        client.get(f"/api/v1/cases/{case['id']}", headers=VIEWER).json()["status"]
        == "awaiting_review"
    )

    # Screening before review / manual entry: facts missing or unconfirmed -> never "eligible".
    first = client.post(f"/api/v1/cases/{case['id']}/screenings", headers=ANALYST)
    assert first.status_code == 201
    assert first.json()["outcome"] == "insufficient_evidence"
    assert first.json()["status"] == "needs_review"
    reg5 = next(
        r
        for r in first.json()["mandatory_results"]
        if r["rule_id"] == "ICDR_REG5_INELIGIBLE_ENTITIES"
    )
    assert reg5["verdict"] == "inconclusive" and reg5["missing_inputs"]

    # Analysts cannot resolve review items; reviewers can.
    item = next(i for i in items if i["field_path"] == "declarations.debarred_by_sebi")
    assert (
        client.post(
            f"/api/v1/review-items/{item['id']}/resolve",
            json={"action": "confirm"},
            headers=ANALYST,
        ).status_code
        == 403
    )
    for it in items:
        r = client.post(
            f"/api/v1/review-items/{it['id']}/resolve",
            json={"action": "confirm", "reason": "checked against p.3"},
            headers=REVIEWER,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "confirmed"
    # resolving twice is rejected
    assert (
        client.post(
            f"/api/v1/review-items/{item['id']}/resolve",
            json={"action": "confirm"},
            headers=REVIEWER,
        ).status_code
        == 409
    )

    # Fill remaining facts manually (issue structure, promoter, Reg 5/6(1)(d) declarations).
    updates = [
        {"field_path": "declarations.promoter_or_director_of_debarred_company", "value": False},
        {"field_path": "declarations.outstanding_convertibles_not_exempt", "value": False},
        {"field_path": "declarations.name_changed_within_last_year", "value": False},
        {"field_path": "promoter.post_issue_holding", "value": "55"},
        {"field_path": "promoter.lock_in_months", "value": 18},
        {"field_path": "issue_details.issue_size", "value": "250"},
        {"field_path": "issue_details.post_issue_paid_up_capital", "value": "20"},
        {"field_path": "issue_details.expected_market_cap", "value": "1200"},
        {"field_path": "issue_details.public_offer_percentage", "value": "25"},
    ]
    r = client.patch(
        f"/api/v1/cases/{case['id']}/fields", json={"updates": updates}, headers=ANALYST
    )
    assert r.status_code == 200, r.text
    r2 = client.patch(
        f"/api/v1/cases/{case['id']}/data".replace("/data", "/fields"),
        json={"updates": [{"field_path": "promoter.is_capex_issue", "value": False}]},
        headers=ANALYST,
    )
    assert r2.status_code == 422  # not an addressable ExtractedValue field
    payload = client.get(f"/api/v1/cases/{case['id']}/data", headers=VIEWER).json()["payload"]
    payload["promoter"]["is_capex_issue"] = False
    put = client.put(
        f"/api/v1/cases/{case['id']}/data",
        json={"payload": payload, "reason": "capex flag"},
        headers=ANALYST,
    )
    assert put.status_code == 200

    second = client.post(f"/api/v1/cases/{case['id']}/screenings", headers=ANALYST).json()
    mandatory = {r["rule_id"]: r["verdict"] for r in second["mandatory_results"]}
    assert mandatory["NTA_3CR"] == "pass"
    assert mandatory["AVG_OPERATING_PROFIT_15CR"] == "pass"  # 32.1, 21.005, 19.5025 -> avg 24.2
    assert mandatory["ICDR_REG5_INELIGIBLE_ENTITIES"] == "pass"
    assert second["outcome"] == "no_failure_identified", [
        (r["rule_id"], r["verdict"], r["missing_inputs"]) for r in second["mandatory_results"]
    ]
    nta_rule = next(r for r in second["mandatory_results"] if r["rule_id"] == "NTA_3CR")
    ev = nta_rule["evidence"][-1]
    assert (
        ev["page_number"] == 2 and ev["original_unit"] == "INR_LAKH" and ev["kind"] == "extracted"
    )

    reports = client.get(f"/api/v1/cases/{case['id']}/screenings", headers=VIEWER).json()
    assert len(reports) == 2 and reports[0]["data_version"] > reports[1]["data_version"]
    html = client.get(
        f"/api/v1/reports/{second['report_id']}/export", params={"format": "html"}, headers=VIEWER
    )
    assert html.status_code == 200 and "C. Evidence register" in html.text
    assert "default-src 'none'" in html.headers["content-security-policy"]

    sign = {
        "reviewer_name": "R. Reviewer",
        "final_decision": "proceed",
        "rationale": "Checked.",
        "conditions": [],
    }
    assert (
        client.post(
            f"/api/v1/reports/{second['report_id']}/sign-off", json=sign, headers=ANALYST
        ).status_code
        == 403
    )
    signed = client.post(
        f"/api/v1/reports/{second['report_id']}/sign-off", json=sign, headers=REVIEWER
    )
    assert signed.status_code == 200 and signed.json()["review"]["status"] == "completed"
    assert (
        client.post(
            f"/api/v1/reports/{second['report_id']}/sign-off", json=sign, headers=REVIEWER
        ).status_code
        == 409
    )

    history = client.get(f"/api/v1/cases/{case['id']}/history", headers=VIEWER).json()
    actions = {h["action"] for h in history}
    assert {
        "case.created",
        "document.uploaded",
        "document.extracted",
        "review_item.confirm",
        "case.fields_set",
        "report.created",
    } <= actions
    versions = client.get(f"/api/v1/cases/{case['id']}/data/versions", headers=VIEWER).json()
    assert [v["version"] for v in versions] == sorted(
        (v["version"] for v in versions), reverse=True
    )

    dash = client.get("/api/v1/dashboard", headers=VIEWER).json()
    assert dash["cases_total"] == 1 and dash["reports_total"] == 2


def test_correction_preserves_original_and_requires_reason(app_factory: Any) -> None:
    client = _client(app_factory)
    case = _case(client)
    _upload(client, case["id"], standard_drhp())
    item = client.get(
        "/api/v1/review-items", params={"case_id": case["id"]}, headers=VIEWER
    ).json()[0]
    no_reason = client.post(
        f"/api/v1/review-items/{item['id']}/resolve",
        json={"action": "correct", "value": True},
        headers=REVIEWER,
    )
    assert no_reason.status_code == 422
    fixed = client.post(
        f"/api/v1/review-items/{item['id']}/resolve",
        json={"action": "correct", "value": True, "reason": "SEBI order dated ..."},
        headers=REVIEWER,
    ).json()
    event = fixed["history"][-1]
    assert event["original_value"]["value"] is False  # original extraction preserved in the event
    assert (
        event["new_value"]["value"] is True
        and event["new_value"]["extraction_method"] == "human_corrected"
    )
    assert event["actor"] == "rev"
    assert any("Corrected by rev" in n for n in event["new_value"]["notes"])


def test_human_values_are_not_overwritten_by_extraction(app_factory: Any) -> None:
    client = _client(app_factory)
    case = _case(client)
    client.patch(
        f"/api/v1/cases/{case['id']}/fields",
        headers=ANALYST,
        json={
            "updates": [
                {
                    "field_path": "financials.fiscal_years[FY2024].net_worth",
                    "value": "149",
                    "period_end": "2024-03-31",
                }
            ]
        },
    )
    _upload(client, case["id"], standard_drhp())
    payload = client.get(f"/api/v1/cases/{case['id']}/data", headers=VIEWER).json()["payload"]
    fy = next(f for f in payload["financials"]["fiscal_years"] if f["year_label"] == "FY2024")
    assert fy["net_worth"]["value"] == "149" and fy["net_worth"]["extraction_method"] == "manual"
    items = client.get(
        "/api/v1/review-items", params={"case_id": case["id"]}, headers=VIEWER
    ).json()
    conflict = next(
        i for i in items if i["field_path"] == "financials.fiscal_years[FY2024].net_worth"
    )
    assert "differs from the human-entered value" in conflict["reason"]


def test_duplicate_upload_is_idempotent(app_factory: Any) -> None:
    client = _client(app_factory)
    case = _case(client)
    pdf = standard_drhp()
    first = _upload(client, case["id"], pdf)
    second = _upload(client, case["id"], pdf)
    assert second["duplicate"] is True and second["id"] == first["id"]
    assert len(client.get(f"/api/v1/cases/{case['id']}/documents", headers=VIEWER).json()) == 1


def test_invalid_uploads_fail_safely(app_factory: Any) -> None:
    client = _client(app_factory, MAX_UPLOAD_SIZE_MB=1)
    case = _case(client)
    url = f"/api/v1/cases/{case['id']}/documents"
    r = client.post(
        url, files={"file": ("x.pdf", b"MZ\x90\x00not a pdf", "application/pdf")}, headers=ANALYST
    )
    assert r.status_code == 415 and r.json()["error"]["details"]["reason"] == "not_pdf"
    r = client.post(
        url,
        files={"file": ("x.pdf", b"%PDF-1.7\n" + b"0" * (1024 * 1024 + 10), "application/pdf")},
        headers=ANALYST,
    )
    assert r.status_code == 413
    r = client.post(
        url,
        files={"file": ("x.pdf", b"%PDF-1.4\ngarbage only", "application/pdf")},
        headers=ANALYST,
    )
    assert r.status_code == 422 and r.json()["error"]["details"]["reason"] == "corrupt"
    import io

    import pikepdf

    pdf = pikepdf.new()
    pdf.add_blank_page()
    buf = io.BytesIO()
    pdf.save(buf, encryption=pikepdf.Encryption(user="u", owner="o"))
    r = client.post(
        url, files={"file": ("x.pdf", buf.getvalue(), "application/pdf")}, headers=ANALYST
    )
    assert r.status_code == 422 and r.json()["error"]["details"]["reason"] == "encrypted"
    assert client.get(url, headers=VIEWER).json() == []  # nothing stored


def test_unsafe_filename_is_sanitised(app_factory: Any) -> None:
    client = _client(app_factory)
    case = _case(client)
    doc = _upload(client, case["id"], standard_drhp(), name="../../etc/passwd<script>.pdf")
    assert doc["filename"] == "passwd_script_.pdf"
    content = client.get(f"/api/v1/documents/{doc['id']}/content", headers=VIEWER)
    assert content.headers["content-type"] == "application/pdf"
    assert content.headers["content-security-policy"] == "sandbox"


def test_page_preview_and_retention(app_factory: Any) -> None:
    client = _client(app_factory)
    case = _case(client)
    doc = _upload(client, case["id"], standard_drhp())
    img = client.get(f"/api/v1/documents/{doc['id']}/pages/2/image", headers=VIEWER)
    assert img.status_code == 200 and img.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert (
        client.get(f"/api/v1/documents/{doc['id']}/pages/9/image", headers=VIEWER).status_code
        == 404
    )
    deleted = client.delete(f"/api/v1/documents/{doc['id']}/content", headers=ANALYST).json()
    assert deleted["content_retained"] is False
    assert client.get(f"/api/v1/documents/{doc['id']}/content", headers=VIEWER).status_code == 409
    assert client.post(f"/api/v1/documents/{doc['id']}/retry", headers=ANALYST).status_code == 409


def test_auth_roles_and_unknown_ids(app_factory: Any) -> None:
    client = _client(app_factory)
    assert client.get("/api/v1/cases").status_code == 401
    assert (
        client.post("/api/v1/cases", json={"company_name": "X"}, headers=VIEWER).status_code == 403
    )
    missing = client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000", headers=VIEWER)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"
    assert missing.json()["error"]["request_id"]
    bad = client.get("/api/v1/cases/not-a-uuid", headers=VIEWER)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get("/api/v1/system/health").status_code == 200  # liveness needs no auth


def test_sme_route_case_is_unsupported_scope(app_factory: Any) -> None:
    client = _client(app_factory)
    r = client.post(
        "/api/v1/cases",
        json={"company_name": "Small Co", "listing_route": "sme_chapter_ix"},
        headers=ANALYST,
    )
    report = client.post(f"/api/v1/cases/{r.json()['id']}/screenings", headers=ANALYST).json()
    assert report["outcome"] == "unsupported_scope" and report["status"] == "needs_review"


def test_capabilities_and_rules(app_factory: Any) -> None:
    client = _client(app_factory)
    caps = client.get("/api/v1/system/capabilities", headers=VIEWER).json()
    assert caps["external_services"] == [] and caps["auth"]["enabled"] is True
    assert (
        caps["ruleset"]["version"] == "2.0.0" and caps["ruleset"]["legal_review_confirmed"] is False
    )
    rules = client.get("/api/v1/rules", headers=VIEWER).json()["rules"]
    nta = next(r for r in rules if r["rule_id"] == "NTA_3CR")
    assert nta["sources"][0]["document_sha256"]
    rulesets = client.get("/api/v1/rulesets", headers=VIEWER).json()
    assert {r["version"]: r["status"] for r in rulesets} == {
        "1.0.0": "superseded",
        "2.0.0": "active",
    }


def test_upload_rate_limit(app_factory: Any) -> None:
    client = _client(app_factory, UPLOAD_RATE_LIMIT_PER_MINUTE=2)
    case = _case(client)
    url = f"/api/v1/cases/{case['id']}/documents"
    codes = [
        client.post(
            url, files={"file": ("x.pdf", b"nope", "application/pdf")}, headers=ANALYST
        ).status_code
        for _ in range(3)
    ]
    assert codes == [415, 415, 429]


def test_interrupted_jobs_are_recovered_on_restart(app_factory: Any) -> None:
    from app.db.models import DocumentRow

    client = _client(app_factory)
    case = _case(client)
    doc = _upload(client, case["id"], standard_drhp())
    container = client.app.state.container  # type: ignore[attr-defined]
    with container.db.session() as s:
        s.get(DocumentRow, doc["id"]).status = "extracting"
    assert container.documents.recover_interrupted() == 1
    after = client.get(f"/api/v1/documents/{doc['id']}", headers=VIEWER).json()
    assert after["status"] == "failed" and after["error_code"] == "INTERRUPTED"
    retried = client.post(f"/api/v1/documents/{doc['id']}/retry", headers=ANALYST).json()
    assert retried["status"] in ("completed", "awaiting_review") and retried["attempts"] == 2

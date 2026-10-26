import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from redherring.cli import main
from redherring.ingest.manifest import DocType, Manifest, ManifestEntry, Platform, sha256_file
from tests.pdfgen import PageSpec, build_pdf


def _statement_page() -> PageSpec:
    p = PageSpec()
    p.text(72, 60, "(Rs. in Lakhs)", 8)
    p.grid(
        72,
        80,
        [220, 110, 110],
        [
            ["Particulars", "For the year ended March 31, 2026", "For the year ended March 31, 2025"],  # noqa: E501
            ["Revenue from operations", "1,000.50", "900.25"],
            ["Other income", "12.75", "9.10"],
            ["Total income", "1,013.25", "909.35"],
        ],
    )  # fmt: skip
    return p


def _register(tmp_path: Path, doc_id: str, pdf: bytes) -> None:
    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    path = raw / f"{doc_id}.pdf"
    path.write_bytes(pdf)
    Manifest(tmp_path / "manifest.jsonl").add(
        ManifestEntry(
            doc_id=doc_id,
            url="https://example.invalid/x.pdf",
            issuer="Demo Ltd",
            doc_type=DocType.PROSPECTUS,
            platform=Platform.MAINBOARD,
            sha256=sha256_file(path),
            size_bytes=path.stat().st_size,
            fetched_at=datetime.now(UTC),
            local_path=f"raw/{doc_id}.pdf",
            content_type="application/pdf",
        )
    )


def test_analyze_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _register(tmp_path, "demo", build_pdf([_statement_page()]))
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    capsys.readouterr()
    assert main(["--data-dir", str(tmp_path), "analyze"]) == 0
    out = capsys.readouterr().out
    assert "| demo |" in out

    report = json.loads((tmp_path / "extracted" / "demo.financials.json").read_text())
    concepts = {v["concept"] for v in report["values"]}
    assert {"revenue_from_operations", "other_income", "total_income"} <= concepts
    assert all(v["verified"] for v in report["values"])  # every value re-found in the PDF text
    assert all(v["pdf_page"] == 1 for v in report["values"])
    assert report["summary"]["footing_checked"] == 2  # one identity, two periods
    assert report["summary"]["footing_passed"] == 2
    assert report["summary"]["values_verified"] == report["summary"]["values_total"]


def test_analyze_requires_parsed_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _register(tmp_path, "demo", build_pdf([_statement_page()]))
    assert main(["--data-dir", str(tmp_path), "analyze"]) == 1
    assert "run `rh parse` first" in capsys.readouterr().err


def _offer_page() -> PageSpec:
    p = PageSpec()
    p.text(72, 60, "FRESH ISSUE OF 100,000 EQUITY SHARES AGGREGATING TO Rs. 1,000 MILLION", 8)
    p.text(72, 100, "OBJECTS OF THE ISSUE", 9)
    p.text(72, 116, "(Rs. in million)", 8)
    p.grid(
        72,
        130,
        [260, 120],
        [
            ["Particulars", "Estimated amount"],
            ["Repayment of borrowings", "700.00"],
            ["General corporate purposes", "240.00"],
            ["Net Proceeds", "940.00"],
        ],
    )
    return p


def test_analyze_raises_a_cited_flag_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _register(tmp_path, "demo", build_pdf([_offer_page()]))
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    capsys.readouterr()
    assert main(["--data-dir", str(tmp_path), "analyze"]) == 0
    out = capsys.readouterr().out
    assert "| demo |" in out

    report = json.loads((tmp_path / "extracted" / "demo.financials.json").read_text())
    keys = {f["key"] for f in report["issue_facts"]}
    assert {"issue.fresh_issue_amount", "objects.gcp_amount"} <= keys
    assert all(f["verified"] for f in report["issue_facts"])
    (flag,) = [f for f in report["flags"] if f["rule_id"] == "OBJ-GCP-CAP-MAINBOARD"]
    assert flag["severity"] == "medium"
    assert "24%" in flag["explanation"]
    assert flag["citations"] and all(c["pdf_page"] == 1 for c in flag["citations"])
    assert flag["sources"][0]["clause"] == "Regulation 7(2)"
    (debt,) = [f for f in report["flags"] if f["rule_id"] == "OBJ-DEBT-REPAYMENT-SHARE"]
    assert debt["severity"] == "low" and debt["heuristic"]
    assert "70%" in debt["explanation"]  # 700 of the 1,000 million fresh issue
    assert report["summary"]["flags"] == 2
    assert report["summary"]["issue_facts_verified"] == report["summary"]["issue_facts_total"]


def test_a_summed_repayment_fact_is_verified_part_by_part_and_a_bad_part_fails(
    tmp_path: Path,
) -> None:
    from redherring.analyze import analyze_document
    from redherring.parse.pdf import parse_pdf

    p = PageSpec()
    p.text(72, 60, "FRESH ISSUE OF 100,000 EQUITY SHARES AGGREGATING TO Rs. 1,000 MILLION", 8)
    p.text(72, 100, "OBJECTS OF THE ISSUE", 9)
    p.text(72, 116, "(Rs. in million)", 8)
    p.grid(
        72, 130, [260, 120],
        [
            ["Particulars", "Estimated amount"],
            ["Repayment of borrowings by our Company", "300.00"],
            ["Repayment of borrowings by our Subsidiary", "200.00"],
            ["General corporate purposes", "100.00"],
            ["Net Proceeds", "600.00"],
        ],
    )  # fmt: skip
    path = tmp_path / "sum.pdf"
    path.write_bytes(build_pdf([p]))
    report = analyze_document(parse_pdf(path), path, platform="mainboard")
    debt = next(f for f in report.issue_facts if f.key.value == "objects.debt_repayment_amount")
    assert debt.value == 500_000_000 and debt.verified, debt.failures

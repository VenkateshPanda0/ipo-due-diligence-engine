from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from redherring.cli import main
from redherring.ingest.manifest import DocType, Manifest, ManifestEntry, Platform, sha256_file
from tests.pdfgen import PageSpec, build_pdf


def _add(tmp_path: Path, doc_id: str, doc_type: DocType, million: int, filed: date) -> None:
    p = PageSpec()
    p.text(
        72, 60, f"FRESH ISSUE OF 100,000 EQUITY SHARES AGGREGATING TO Rs. {million:,} MILLION", 8
    )
    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    pdf = raw / f"{doc_id}.pdf"
    pdf.write_bytes(build_pdf([p]))
    Manifest(tmp_path / "manifest.jsonl").add(
        ManifestEntry(
            doc_id=doc_id,
            url=f"https://example.invalid/{doc_id}.pdf",
            issuer="Demo Ltd",
            doc_type=doc_type,
            platform=Platform.MAINBOARD,
            filing_date=filed,
            sha256=sha256_file(pdf),
            size_bytes=pdf.stat().st_size,
            fetched_at=datetime.now(UTC),
            local_path=f"raw/{doc_id}.pdf",
            content_type="application/pdf",
        )
    )


def test_diff_command_writes_a_page_and_lists_the_figures_that_moved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _add(tmp_path, "drhp", DocType.DRHP, 1000, date(2025, 1, 5))
    _add(tmp_path, "rhp", DocType.RHP, 800, date(2025, 6, 5))
    base = ["--data-dir", str(tmp_path)]
    assert main([*base, "parse"]) == 0
    assert main([*base, "analyze"]) == 0
    capsys.readouterr()
    assert main([*base, "diff", "drhp", "rhp"]) == 0
    out = capsys.readouterr().out
    assert "issue.fresh_issue_amount" in out
    html = (tmp_path / "reports" / "diff_drhp__rhp.html").read_text()
    assert "changed -20.0%" in html
    assert "Not investment advice" in html


def test_diff_command_names_an_unknown_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _add(tmp_path, "only", DocType.RHP, 800, date(2025, 6, 5))
    assert main(["--data-dir", str(tmp_path), "diff", "only", "ghost"]) == 1
    assert "ghost" in capsys.readouterr().err

from pathlib import Path

import pytest

from redherring.cli import main
from redherring.ingest.manifest import DocType, Manifest, ManifestEntry, Platform, sha256_file
from tests.pdfgen import PageSpec, build_pdf


def test_unimplemented_commands_exit_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["analyze"]) == 2
    assert "not implemented" in capsys.readouterr().err


def test_parse_command_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from datetime import UTC, datetime

    raw = tmp_path / "raw"
    raw.mkdir()
    pdf = raw / "demo.pdf"
    pdf.write_bytes(build_pdf([PageSpec().text(72, 72, "Objects of the Issue")]))
    Manifest(tmp_path / "manifest.jsonl").add(
        ManifestEntry(
            doc_id="demo",
            url="https://example.invalid/demo.pdf",
            issuer="Demo Ltd",
            doc_type=DocType.PROSPECTUS,
            platform=Platform.SME,
            sha256=sha256_file(pdf),
            size_bytes=pdf.stat().st_size,
            fetched_at=datetime.now(UTC),
            local_path="raw/demo.pdf",
            content_type="application/pdf",
        )
    )
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    assert "| demo |" in capsys.readouterr().out
    assert "[PDF_PAGE_1]" in (tmp_path / "parsed" / "demo.tagged.txt").read_text()
    assert (tmp_path / "parsed" / "demo.json").exists()

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


def _register(tmp_path: Path, doc_id: str, content: bytes) -> None:
    from datetime import UTC, datetime

    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    pdf = raw / f"{doc_id}.pdf"
    pdf.write_bytes(content)
    Manifest(tmp_path / "manifest.jsonl").add(
        ManifestEntry(
            doc_id=doc_id,
            url=f"https://example.invalid/{doc_id}.pdf",
            issuer="Demo Ltd",
            doc_type=DocType.PROSPECTUS,
            platform=Platform.SME,
            sha256=sha256_file(pdf),
            size_bytes=pdf.stat().st_size,
            fetched_at=datetime.now(UTC),
            local_path=f"raw/{doc_id}.pdf",
            content_type="application/pdf",
        )
    )


def test_parse_continues_past_a_corrupt_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _register(tmp_path, "bad", b"%PDF-1.4\nthis is not a real pdf\n")
    _register(tmp_path, "good", build_pdf([PageSpec().text(72, 72, "Objects of the Issue")]))
    assert main(["--data-dir", str(tmp_path), "parse"]) == 1  # non-zero: one failure
    captured = capsys.readouterr()
    assert "FAIL  bad" in captured.err
    assert "| good |" in captured.out
    assert (tmp_path / "parsed" / "good.json").exists()
    assert not (tmp_path / "parsed" / "bad.json").exists()


def test_parse_reuses_output_when_hash_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _register(tmp_path, "good", build_pdf([PageSpec().text(72, 72, "Objects of the Issue")]))
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    capsys.readouterr()
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    assert "cached good" in capsys.readouterr().err
    assert main(["--data-dir", str(tmp_path), "parse", "--force"]) == 0
    assert "parsed good" in capsys.readouterr().err


def test_parse_ignores_output_from_older_parser_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    _register(tmp_path, "good", build_pdf([PageSpec().text(72, 72, "Objects of the Issue")]))
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    out = tmp_path / "parsed" / "good.json"
    data = json.loads(out.read_text())
    data["parser_version"] = 0  # as written by a pre-versioning parser
    out.write_text(json.dumps(data))
    capsys.readouterr()
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    assert "parsed good" in capsys.readouterr().err  # re-parsed, not "cached"


def test_parse_skips_regulations_unless_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _register(tmp_path, "filing", build_pdf([PageSpec().text(72, 72, "Objects of the Issue")]))
    _register(tmp_path, "icdr", build_pdf([PageSpec().text(72, 72, "Regulation 7")]))
    m = Manifest(tmp_path / "manifest.jsonl")
    m.add(m.get("icdr").model_copy(update={"doc_type": DocType.REGULATION}))  # type: ignore[union-attr]
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    out = capsys.readouterr().out
    assert "| filing |" in out
    assert "| icdr |" not in out
    assert main(["--data-dir", str(tmp_path), "parse", "--doc-id", "icdr"]) == 0
    assert "| icdr |" in capsys.readouterr().out

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from redherring.cli import main
from redherring.ingest.manifest import DocType, Manifest, ManifestEntry, Platform, sha256_file
from tests.pdfgen import PageSpec, build_pdf


def _setup(tmp_path: Path) -> str:
    p = PageSpec()
    p.text(72, 60, "FRESH ISSUE OF 100,000 EQUITY SHARES AGGREGATING TO Rs. 1,000 MILLION", 8)
    raw = tmp_path / "raw"
    raw.mkdir()
    pdf = raw / "demo.pdf"
    pdf.write_bytes(build_pdf([p]))
    sha = sha256_file(pdf)
    Manifest(tmp_path / "manifest.jsonl").add(
        ManifestEntry(
            doc_id="demo",
            url="https://example.invalid/demo.pdf",
            issuer="Demo Ltd",
            doc_type=DocType.PROSPECTUS,
            platform=Platform.MAINBOARD,
            sha256=sha,
            size_bytes=pdf.stat().st_size,
            fetched_at=datetime.now(UTC),
            local_path="raw/demo.pdf",
            content_type="application/pdf",
        )
    )
    assert main(["--data-dir", str(tmp_path), "parse"]) == 0
    assert main(["--data-dir", str(tmp_path), "analyze"]) == 0
    return sha


def _final_label(sha: str, *, raw: str = "1,000", value: str = "1000000000") -> dict[str, object]:
    return {
        "doc_id": "demo",
        "doc_sha256": sha,
        "labelled_by": "tester",
        "labelled_on": "2026-10-24",
        "method": "read from the PDF text",
        "fields": [
            {
                "key": "issue.fresh_issue_amount",
                "status": "present",
                "value_rupees": value,
                "raw": raw,
                "pages": [1],
                "span": "AGGREGATING TO Rs. 1,000 MILLION",
            },
            {"key": "issue.ofs_amount", "status": "absent"},
        ],
    }


def test_label_init_prefills_a_draft_from_the_extractor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _setup(tmp_path)
    labels = tmp_path / "labels"
    assert main(["--data-dir", str(tmp_path), "label-init", "--labels-dir", str(labels)]) == 0
    draft = json.loads((labels / "demo.draft.json").read_text())
    (f,) = [x for x in draft["fields"] if x["key"] == "issue.fresh_issue_amount"]
    assert f["status"] == "unreviewed"
    assert f["suggested_rupees"] == "1000000000"
    assert f["pages"] == [1]
    # refuses to clobber an existing draft
    assert main(["--data-dir", str(tmp_path), "label-init", "--labels-dir", str(labels)]) == 1


def test_label_check_and_eval_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sha = _setup(tmp_path)
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "demo.json").write_text(json.dumps(_final_label(sha)))
    base = ["--data-dir", str(tmp_path)]
    assert main([*base, "label-check", "--labels-dir", str(labels)]) == 0
    capsys.readouterr()
    assert main([*base, "eval", "--labels-dir", str(labels)]) == 0
    out = capsys.readouterr().out
    assert "value accuracy" in out.lower()
    report = json.loads((tmp_path / "eval" / "report.json").read_text())
    assert report["correct"] == 1
    assert report["correct_abstentions"] == 1
    assert report["value_accuracy"] == 1.0
    assert report["citation_accuracy"] == 1.0
    assert report["hallucination_rate"] == 0.0


def test_label_check_catches_a_label_that_is_not_on_the_page(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sha = _setup(tmp_path)
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "demo.json").write_text(json.dumps(_final_label(sha, raw="9,999")))
    assert main(["--data-dir", str(tmp_path), "label-check", "--labels-dir", str(labels)]) == 1
    assert "not found on cited page 1" in capsys.readouterr().err


def test_label_check_rejects_a_label_for_a_different_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _setup(tmp_path)
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "demo.json").write_text(json.dumps(_final_label("0" * 64)))
    assert main(["--data-dir", str(tmp_path), "label-check", "--labels-dir", str(labels)]) == 1
    assert "sha256" in capsys.readouterr().err


def test_eval_without_labels_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _setup(tmp_path)
    (tmp_path / "labels").mkdir()
    assert (
        main(["--data-dir", str(tmp_path), "eval", "--labels-dir", str(tmp_path / "labels")]) == 1
    )
    assert "no label files" in capsys.readouterr().err


def test_stale_analysis_output_gives_a_clear_message_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sha = _setup(tmp_path)
    out = tmp_path / "extracted" / "demo.financials.json"
    data = json.loads(out.read_text())
    del data["facts"]  # as written by an older version
    data["analysis_version"] = 0
    out.write_text(json.dumps(data))
    labels = tmp_path / "labels"
    labels.mkdir()
    (labels / "demo.json").write_text(json.dumps(_final_label(sha)))
    assert main(["--data-dir", str(tmp_path), "eval", "--labels-dir", str(labels)]) == 1
    err = capsys.readouterr().err
    assert "re-run `rh analyze`" in err
    assert "Traceback" not in err

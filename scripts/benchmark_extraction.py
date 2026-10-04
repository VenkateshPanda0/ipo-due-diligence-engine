"""
Real-document extraction benchmark.

Runs the document-intelligence pipeline on public DRHPs listed in
benchmark/manifest.json and scores the output against independently prepared
answer keys in benchmark/ground_truth/. PDFs are not committed (see --download).

Usage (from repo root):
    .venv/bin/python scripts/benchmark_extraction.py --download      # fetch PDFs, verify SHA-256
    .venv/bin/python scripts/benchmark_extraction.py --run [--split holdout] [--ocr off]
Writes docs/BENCHMARK_RESULTS.md and benchmark/results/latest.json.

Metric definitions (denominator = expected fields of the selected documents):
  correct            selected value equals the expected value within half a unit of the
                     printed precision, and the cited page is one of the expected pages
  wrong              a value was selected but differs (any status)
  false_high         wrong AND status EXTRACTED_HIGH_CONFIDENCE  (the dangerous case)
  flagged            status is needs-verification or conflicting (whether right or wrong)
  missing            no value selected (NOT_FOUND / unit-unknown abstention)
  correct_abstention for fields whose expected unit is undeclared: no normalised value
                     was produced (counted as correct behaviour, reported separately)
  precision = correct / (correct + wrong);  recall = correct / scored fields
  route_correct      the Reg 6(1)/6(2) suggestion matches the document's stated route
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.intelligence.pipeline import PipelineConfig, run_pipeline  # noqa: E402

BENCH = ROOT / "benchmark"
DOCS = BENCH / "documents"
SPLITS = {
    # The 2026-10-04 holdout (iberia, vardaan, anchor) was measured once (21/36) and then
    # moved here for failure analysis; see docs/BENCHMARK.md.
    "development": [
        "madhur-iron-and-steel-india-limited-drhp",
        "ekkaa-electronics-india-limited-drhp",
        "jsw-one-platforms-limited-drhp",
        "iris-global-services-limited-drhp",
        "jagatjit-agri-engineering-limited-drhp",
        "iberia-pharmaceuticals-india-limited-drhp",
        "vardaan-biotech-limited-drhp",
        "anchor-offshore-services-limited-drhp",
    ],
    # Fresh holdout: added after the code freeze, never used for tuning.
    "holdout": [
        "royal-chain-limited-drhp",
        "hi-tech-flow-solutions-limited-drhp",
        "m-k-c-agro-fresh-limited-drhp",
        "maharashtra-oil-extractions-limited-drhp",
        "ultravibrant-integrated-energy-limited-drhp",
    ],
}


def load_manifest() -> list[dict]:
    return json.loads((BENCH / "manifest.json").read_text())["documents"]


def download() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    for doc in load_manifest():
        path = DOCS / f"{doc['id']}.pdf"
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != doc["sha256"]:
            print(f"downloading {doc['id']} …")
            req = urllib.request.Request(doc["pdf_url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310 (fixed official URL)
                path.write_bytes(resp.read())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{doc['id']}: {'OK' if digest == doc['sha256'] else 'SHA-256 MISMATCH'}")


def tolerance(original: str, unit: str) -> Decimal:
    digits = original.strip("()").split(".")[1] if "." in original else ""
    factor = {"INR_LAKH": Decimal("0.01"), "INR_MILLION": Decimal("0.1")}[unit]
    return Decimal(5) / Decimal(10) ** (len(digits) + 1) * factor


def score_document(doc_id: str, result: object) -> dict:
    gt = json.loads((BENCH / "ground_truth" / f"{doc_id}.json").read_text())
    outcomes = {o.field_path: o for o in result.outcomes}  # type: ignore[attr-defined]
    rows = []
    for exp in gt["fields"]:
        o = outcomes.get(exp["field_path"])
        sel = o.selected if o else None
        status = o.status.value if o else "not_found"
        row = {
            "field_path": exp["field_path"],
            "expected": exp["expected_crore"],
            "original": exp["original_text"],
            "status": status,
            "got": sel["value"] if sel else None,
            "page": sel.get("page_number") if sel else None,
            "expected_pages": exp["pages"],
            "got_unit": sel.get("original_unit") if sel else None,
            "got_basis": sel.get("statement_basis") if sel else None,
            "expected_basis": exp["basis"],
        }
        if exp["expected_crore"] is None:
            row["outcome"] = "correct_abstention" if sel is None else "wrong_normalisation"
        elif sel is None:
            row["outcome"] = "missing"
        else:
            ok_value = abs(Decimal(sel["value"]) - Decimal(exp["expected_crore"])) <= tolerance(
                exp["original_text"], exp["original_unit"]
            )
            ok_page = sel.get("page_number") in exp["pages"]
            row["outcome"] = (
                "correct" if ok_value and ok_page else ("wrong_page" if ok_value else "wrong")
            )
        row["high"] = status == "extracted_high_confidence"
        rows.append(row)
    sugg = result.suggestions.get("listing_route", {}).get("value")  # type: ignore[attr-defined]
    return {
        "document_id": doc_id,
        "expected_route": gt["expected_route"],
        "suggested_route": sugg,
        "route_correct": sugg == gt["expected_route"],
        "fields": rows,
        "metrics": result.metrics,
        "warnings": result.warnings[:10],
    }  # type: ignore[attr-defined]


def summarise(docs: list[dict]) -> dict:
    rows = [r for d in docs for r in d["fields"]]
    scored = [r for r in rows if r["expected"] is not None]
    correct = sum(r["outcome"] == "correct" for r in scored)
    wrong = sum(r["outcome"] in ("wrong", "wrong_page") for r in scored)
    false_high = sum(r["outcome"] in ("wrong", "wrong_page") and r["high"] for r in scored)
    flagged = sum(
        r["status"] in ("extracted_needs_verification", "conflicting_candidates") for r in scored
    )
    missing = sum(r["outcome"] == "missing" for r in scored)
    correct_high = sum(r["outcome"] == "correct" and r["high"] for r in scored)
    abst = [r for r in rows if r["expected"] is None]
    by_field: dict[str, dict[str, int]] = {}
    for r in scored:
        f = r["field_path"].split(".")[-1]
        b = by_field.setdefault(
            f, {"expected": 0, "correct": 0, "wrong": 0, "missing": 0, "false_high": 0}
        )
        b["expected"] += 1
        b["correct"] += r["outcome"] == "correct"
        b["wrong"] += r["outcome"] in ("wrong", "wrong_page")
        b["missing"] += r["outcome"] == "missing"
        b["false_high"] += r["outcome"] in ("wrong", "wrong_page") and r["high"]
    n = len(scored) or 1
    return {
        "documents": len(docs),
        "scored_fields": len(scored),
        "correct": correct,
        "wrong": wrong,
        "missing": missing,
        "flagged": flagged,
        "false_high": false_high,
        "correct_high": correct_high,
        "precision": round(correct / (correct + wrong), 4) if correct + wrong else None,
        "recall": round(correct / n, 4),
        "missing_rate": round(missing / n, 4),
        "wrong_rate": round(wrong / n, 4),
        "false_high_rate": round(false_high / n, 4),
        "abstention_cases": len(abst),
        "correct_abstentions": sum(r["outcome"] == "correct_abstention" for r in abst),
        "route_correct": sum(d["route_correct"] for d in docs),
        "by_field": by_field,
    }


def run(split: str, ocr: bool) -> dict:
    ids = SPLITS["development"] + SPLITS["holdout"] if split == "all" else SPLITS[split]
    out = []
    for doc_id in ids:
        path = DOCS / f"{doc_id}.pdf"
        if not path.exists():
            print(f"skip {doc_id}: not downloaded")
            continue
        t0 = time.monotonic()
        result = run_pipeline(
            path.read_bytes(),
            filename=path.name,
            document_id=doc_id,
            company_name=doc_id,
            config=PipelineConfig(ocr_enabled=ocr, max_ocr_pages=30, timeout_s=1800),
        )
        scored = score_document(doc_id, result)
        scored["seconds"] = round(time.monotonic() - t0, 1)
        scored["split"] = "holdout" if doc_id in SPLITS["holdout"] else "development"
        out.append(scored)
        s = summarise([scored])
        print(
            f"{doc_id}: correct {s['correct']}/{s['scored_fields']} wrong {s['wrong']} missing {s['missing']} "
            f"false-high {s['false_high']} route {'ok' if scored['route_correct'] else 'X'} ({scored['seconds']}s)"
        )
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "split": split,
        "ocr": ocr,
        "summary": summarise(out),
        "by_split": {
            k: summarise([d for d in out if d["split"] == k]) for k in ("development", "holdout")
        },
        "documents": out,
    }


def write_report(res: dict) -> None:
    (BENCH / "results").mkdir(exist_ok=True)
    (BENCH / "results" / "latest.json").write_text(json.dumps(res, indent=2, default=str))
    s = res["summary"]
    lines = [
        "# Real-document extraction benchmark — results",
        "",
        f"Generated {res['generated_at']} · split `{res['split']}` · OCR {'on' if res['ocr'] else 'off'}.",
        "Answer keys were prepared by an AI assistant from poppler text and have **not** been verified by a human.",
        "",
        "| Metric | All | Development | Holdout |",
        "|---|---|---|---|",
    ]
    keys = [
        "documents",
        "scored_fields",
        "correct",
        "wrong",
        "missing",
        "flagged",
        "false_high",
        "precision",
        "recall",
        "missing_rate",
        "false_high_rate",
        "correct_abstentions",
        "abstention_cases",
        "route_correct",
    ]
    for k in keys:
        lines.append(
            f"| {k} | {s[k]} | {res['by_split']['development'][k]} | {res['by_split']['holdout'][k]} |"
        )
    lines += [
        "",
        "## By field (all documents)",
        "",
        "| Field | Expected | Correct | Wrong | Missing | False-high |",
        "|---|---|---|---|---|---|",
    ]
    for f, b in sorted(s["by_field"].items()):
        lines.append(
            f"| {f} | {b['expected']} | {b['correct']} | {b['wrong']} | {b['missing']} | {b['false_high']} |"
        )
    lines += [
        "",
        "## By document",
        "",
        "| Document | Split | Correct | Wrong | Missing | Flagged | Route | Seconds |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in res["documents"]:
        ds = summarise([d])
        lines.append(
            f"| {d['document_id']} | {d['split']} | {ds['correct']}/{ds['scored_fields']} | {ds['wrong']} | "
            f"{ds['missing']} | {ds['flagged']} | {'✓' if d['route_correct'] else '✗ (' + str(d['suggested_route']) + ')'} | {d['seconds']} |"
        )
    lines += ["", "## Field-level detail", ""]
    for d in res["documents"]:
        lines += [
            f"### {d['document_id']}",
            "",
            "| Field | Expected (₹ Cr) | Got | Status | Page | Outcome |",
            "|---|---|---|---|---|---|",
        ]
        for r in d["fields"]:
            lines.append(
                f"| {r['field_path'].replace('financials.fiscal_years', '')} | {r['expected']} | {r['got']} | {r['status']} | {r['page']} | {r['outcome']} |"
            )
        lines.append("")
    (ROOT / "docs" / "BENCHMARK_RESULTS.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--download", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--split", choices=["all", "development", "holdout"], default="all")
    p.add_argument("--ocr", choices=["on", "off"], default="on")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    if args.download:
        download()
    if args.run:
        res = run(args.split, args.ocr == "on")
        print(json.dumps({k: v for k, v in res["summary"].items() if k != "by_field"}, indent=1))
        if not args.no_write:
            write_report(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

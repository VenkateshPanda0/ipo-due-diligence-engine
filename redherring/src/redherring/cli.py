"""`rh` command line. M0 implements `ingest` and `parse`; the rest arrive in later milestones."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from redherring.analyze import ANALYSIS_VERSION, AnalysisReport, Summary, analyze_document
from redherring.eval.labels import check_labels, load_labels
from redherring.eval.metrics import Prediction, score
from redherring.eval.prefill import draft_from_predictions
from redherring.eval.report import eval_markdown
from redherring.ingest.fetch import Fetcher, FetchError
from redherring.ingest.manifest import DocType, Manifest, load_sources
from redherring.parse.models import PARSER_VERSION, ParsedDocument
from redherring.parse.pdf import default_workers, parse_pdf
from redherring.parse.render import render_tagged
from redherring.parse.report import compute_stats, stats_markdown
from redherring.report_html import report_html
from redherring.report_text import summary_markdown
from redherring.verify.cited import PdfiumPageText

NOT_FILINGS = {DocType.REGULATION, DocType.ENFORCEMENT_ORDER}

NOT_YET = {
    "diff": "M3",
}


def _cmd_ingest(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    manifest = Manifest(data_dir / "manifest.jsonl")
    fetcher = Fetcher(data_dir, min_interval_s=args.min_interval)
    failures = 0
    for spec in load_sources(Path(args.sources)):
        try:
            entry, downloaded = fetcher.fetch(spec, manifest)
        except FetchError as e:
            print(f"FAIL  {spec.doc_id}: {e}", file=sys.stderr)
            failures += 1
            continue
        verb = "fetched" if downloaded else "cached "
        print(f"{verb} {entry.doc_id}  {entry.size_bytes:>11,} B  sha256={entry.sha256[:12]}…")
    return 1 if failures else 0


def _cmd_parse(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    manifest = Manifest(data_dir / "manifest.jsonl")
    entries = manifest.entries()
    if args.doc_id:
        entries = [e for e in entries if e.doc_id in args.doc_id]
    else:  # by default only offer documents; regulations and orders are reference material
        entries = [e for e in entries if e.doc_type not in NOT_FILINGS]
    if not entries:
        print("nothing to parse (run `rh ingest` first, or check --doc-id)", file=sys.stderr)
        return 1
    out_dir = data_dir / "parsed"
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = []
    failures = 0
    for e in entries:
        json_path = out_dir / f"{e.doc_id}.json"
        doc: ParsedDocument | None = None
        if json_path.exists() and not args.force and not args.max_pages:
            cached = ParsedDocument.model_validate_json(json_path.read_text(encoding="utf-8"))
            if cached.sha256 == e.sha256 and cached.parser_version == PARSER_VERSION:
                doc = cached
                print(f"cached {e.doc_id}: parsed output matches sha256", file=sys.stderr)
        if doc is None:
            pages = range(1, args.max_pages + 1) if args.max_pages else None
            try:
                doc = parse_pdf(
                    data_dir / e.local_path,
                    doc_id=e.doc_id,
                    sha256=e.sha256,
                    pages=pages,
                    workers=args.workers,
                )
            except Exception as exc:  # batch boundary: report the bad document, keep going
                print(f"FAIL  {e.doc_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
                failures += 1
                continue
            json_path.write_text(doc.model_dump_json(), encoding="utf-8")
            (out_dir / f"{e.doc_id}.tagged.txt").write_text(render_tagged(doc), encoding="utf-8")
            print(
                f"parsed {e.doc_id}: {doc.n_pages} pages in {doc.parse_seconds}s", file=sys.stderr
            )
            bad = [p.pdf_page for p in doc.pages if p.error]
            if bad:
                print(f"WARN  {e.doc_id}: {len(bad)} page(s) failed: {bad[:10]}", file=sys.stderr)
        stats.append(compute_stats(doc))
    if stats:
        table = stats_markdown(stats)
        (out_dir / "parse_report.md").write_text(table + "\n", encoding="utf-8")
        print(table)
    return 1 if failures else 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    manifest = Manifest(data_dir / "manifest.jsonl")
    entries = [e for e in manifest.entries() if e.doc_type not in NOT_FILINGS]
    if args.doc_id:
        entries = [e for e in entries if e.doc_id in args.doc_id]
    out_dir = data_dir / "extracted"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[Summary] = []
    failures = 0
    for e in entries:
        parsed = data_dir / "parsed" / f"{e.doc_id}.json"
        if not parsed.exists():
            print(f"FAIL  {e.doc_id}: run `rh parse` first", file=sys.stderr)
            failures += 1
            continue
        doc = ParsedDocument.model_validate_json(parsed.read_text(encoding="utf-8"))
        report = analyze_document(
            doc,
            data_dir / e.local_path,
            platform=e.platform.value if e.platform else None,
            as_of=e.filing_date,
        )
        (out_dir / f"{e.doc_id}.financials.json").write_text(
            report.model_dump_json(indent=1), encoding="utf-8"
        )
        rows.append(report.summary)
    if rows:
        table = summary_markdown(rows)
        (out_dir / "summary.md").write_text(table + "\n", encoding="utf-8")
        print(table)
    return 1 if failures else 0


class StaleOutput(RuntimeError):
    pass


def _predictions(data_dir: Path, doc_id: str) -> list[Prediction] | None:
    path = data_dir / "extracted" / f"{doc_id}.financials.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("analysis_version") != ANALYSIS_VERSION:
        raise StaleOutput(f"{path.name} was written by an older analyzer")
    report = AnalysisReport.model_validate(raw)
    return [
        Prediction(key=f.key, value=f.value, pdf_page=f.pdf_page, span=f.span, step=f.step)
        for f in report.facts
    ]


def _cmd_report(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    manifest = Manifest(data_dir / "manifest.jsonl")
    entries = [e for e in manifest.entries() if e.doc_type not in NOT_FILINGS]
    if args.doc_id:
        entries = [e for e in entries if e.doc_id in args.doc_id]
    out_dir = data_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for e in entries:
        path = data_dir / "extracted" / f"{e.doc_id}.financials.json"
        if not path.exists():
            print(f"FAIL  {e.doc_id}: run `rh analyze` first", file=sys.stderr)
            failures += 1
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("analysis_version") != ANALYSIS_VERSION:
            print(
                f"FAIL  {e.doc_id}: written by an older analyzer; re-run `rh analyze`",
                file=sys.stderr,
            )
            failures += 1
            continue
        report = AnalysisReport.model_validate(raw)
        target = out_dir / f"{e.doc_id}.html"
        target.write_text(report_html(report, e), encoding="utf-8")
        print(f"wrote {target}")
    return 1 if failures else 0


def _cmd_label_init(args: argparse.Namespace) -> int:
    data_dir, labels_dir = Path(args.data_dir), Path(args.labels_dir)
    manifest = Manifest(data_dir / "manifest.jsonl")
    entries = [e for e in manifest.entries() if e.doc_type not in NOT_FILINGS]
    if args.doc_id:
        entries = [e for e in entries if e.doc_id in args.doc_id]
    labels_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for e in entries:
        try:
            preds = _predictions(data_dir, e.doc_id)
        except StaleOutput as exc:
            print(f"FAIL  {e.doc_id}: {exc}; re-run `rh analyze`", file=sys.stderr)
            failures += 1
            continue
        out = labels_dir / f"{e.doc_id}.draft.json"
        if preds is None:
            print(f"FAIL  {e.doc_id}: run `rh analyze` first", file=sys.stderr)
            failures += 1
        elif out.exists() and not args.force:
            print(f"FAIL  {out} exists (use --force to overwrite)", file=sys.stderr)
            failures += 1
        else:
            draft = draft_from_predictions(e.doc_id, e.sha256, preds)
            out.write_text(draft.model_dump_json(indent=1), encoding="utf-8")
            print(f"wrote {out} ({len(draft.fields)} fields to review)")
    return 1 if failures else 0


def _cmd_label_check(args: argparse.Namespace) -> int:
    data_dir, labels_dir = Path(args.data_dir), Path(args.labels_dir)
    manifest = Manifest(data_dir / "manifest.jsonl")
    files = load_labels(labels_dir)
    if not files:
        print(f"no label files in {labels_dir}", file=sys.stderr)
        return 1
    bad = 0
    for doc_id, lf in files.items():
        entry = manifest.get(doc_id)
        if entry is None:
            print(f"{doc_id}: not in the manifest", file=sys.stderr)
            bad += 1
            continue
        problems = []
        if lf.doc_sha256 != entry.sha256:
            problems.append(
                f"labels are for sha256 {lf.doc_sha256[:12]}…, manifest has {entry.sha256[:12]}…"
            )
        with PdfiumPageText(data_dir / entry.local_path) as page_text:
            problems += check_labels(lf, page_text)
        for p in problems:
            print(f"{doc_id}: {p}", file=sys.stderr)
        bad += bool(problems)
        if not problems:
            print(f"ok    {doc_id}: {len(lf.fields)} labels")
    return 1 if bad else 0


def _cmd_eval(args: argparse.Namespace) -> int:
    data_dir, labels_dir = Path(args.data_dir), Path(args.labels_dir)
    files = load_labels(labels_dir)
    if not files:
        print(f"no label files in {labels_dir}", file=sys.stderr)
        return 1
    predictions: dict[str, list[Prediction]] = {}
    for doc_id in files:
        try:
            preds = _predictions(data_dir, doc_id)
        except StaleOutput as exc:
            print(f"FAIL  {doc_id}: {exc}; re-run `rh analyze`", file=sys.stderr)
            return 1
        if preds is None:
            print(
                f"WARN  {doc_id}: no extracted output; every labelled value counts as missed",
                file=sys.stderr,
            )
        predictions[doc_id] = preds or []
    report = score(files, predictions)
    out = data_dir / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(report.model_dump_json(indent=1), encoding="utf-8")
    print(eval_markdown(report))
    if {lf.split for lf in files.values()} != {"dev"}:  # only separate when a held-out set exists
        for split, title in (("dev", "Development documents"), ("heldout", "Held-out documents")):
            subset = {d: lf for d, lf in files.items() if lf.split == split}
            if not subset:
                continue
            part = score(subset, {d: predictions[d] for d in subset})
            (out / f"report.{split}.json").write_text(part.model_dump_json(indent=1), "utf-8")
            print(f"\n### {title} ({len(subset)} documents)\n")
            print(eval_markdown(part))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rh", description="RedHerring: IPO offer-document analysis")
    p.add_argument("--data-dir", default="data", help="working data directory (default: data)")
    sub = p.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="download documents listed in a sources TOML")
    ing.add_argument("--sources", default="data/sources.toml")
    ing.add_argument("--min-interval", type=float, default=3.0, help="seconds between requests")
    ing.set_defaults(func=_cmd_ingest)

    par = sub.add_parser("parse", help="parse ingested PDFs into page-tagged blocks and tables")
    par.add_argument("--doc-id", action="append", help="limit to this doc_id (repeatable)")
    par.add_argument("--max-pages", type=int, help="parse only the first N pages")
    par.add_argument(
        "--workers", type=int, default=default_workers(), help="parallel processes per document"
    )
    par.add_argument("--force", action="store_true", help="re-parse even if output is up to date")
    par.set_defaults(func=_cmd_parse)

    ana = sub.add_parser("analyze", help="extract financial values and run verification checks")
    ana.add_argument("--doc-id", action="append", help="limit to this doc_id (repeatable)")
    ana.set_defaults(func=_cmd_analyze)

    rep = sub.add_parser("report", help="write one HTML page per analysed filing")
    rep.add_argument("--doc-id", action="append", help="limit to this doc_id (repeatable)")
    rep.set_defaults(func=_cmd_report)

    lab = sub.add_parser("label-init", help="write draft label files pre-filled from the extractor")
    lab.add_argument("--doc-id", action="append", help="limit to this doc_id (repeatable)")
    lab.add_argument("--labels-dir", default="labels")
    lab.add_argument("--force", action="store_true", help="overwrite an existing draft")
    lab.set_defaults(func=_cmd_label_init)

    chk = sub.add_parser("label-check", help="validate label files against the PDFs")
    chk.add_argument("--labels-dir", default="labels")
    chk.set_defaults(func=_cmd_label_check)

    ev = sub.add_parser("eval", help="score extracted facts against the label files")
    ev.add_argument("--labels-dir", default="labels")
    ev.set_defaults(func=_cmd_eval)

    for name, milestone in NOT_YET.items():
        stub = sub.add_parser(name, help=f"not implemented yet (planned {milestone})")
        stub.set_defaults(func=lambda _a, n=name, m=milestone: _not_yet(n, m))
    return p


def _not_yet(name: str, milestone: str) -> int:
    print(f"`rh {name}` is not implemented yet (planned {milestone}).", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

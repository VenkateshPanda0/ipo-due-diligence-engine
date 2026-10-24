"""`rh` command line. M0 implements `ingest` and `parse`; the rest arrive in later milestones."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from redherring.analyze import Summary, analyze_document
from redherring.ingest.fetch import Fetcher, FetchError
from redherring.ingest.manifest import DocType, Manifest, load_sources
from redherring.parse.models import PARSER_VERSION, ParsedDocument
from redherring.parse.pdf import default_workers, parse_pdf
from redherring.parse.render import render_tagged
from redherring.parse.report import compute_stats, stats_markdown
from redherring.report_text import summary_markdown

NOT_FILINGS = {DocType.REGULATION, DocType.ENFORCEMENT_ORDER}

NOT_YET = {
    "diff": "M3",
    "eval": "M1",
    "report": "M2",
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
        print(summary_markdown(rows))
    return 1 if failures else 0


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

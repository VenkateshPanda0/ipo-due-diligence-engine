# RedHerring

Forensic analysis of Indian IPO offer documents (DRHP / RHP / Prospectus): structured extraction
with page-level citations, a red-flag engine, version diffs, and validation against a labelled
benchmark and post-listing outcomes.

**Status: milestone M0 (skeleton, ingest, parse). No extraction, flags or metrics exist yet,
so this README makes no accuracy claims.**

> Not investment advice. Automated analysis of public disclosures; verify against the source
> document.

This project lives in the `redherring/` folder of the `ipo-due-diligence-engine` repository and is
independent of the code around it (see `docs/decisions.md` for why, and how to split it out).

## What works in M0

| Command | Does |
|---|---|
| `rh ingest` | Downloads the PDFs listed in `data/sources.toml` politely (robots.txt, per-host rate limit, size cap), and records URL, SHA-256, size, fetch time in `data/manifest.jsonl`. Idempotent. |
| `rh parse` | Parses ingested PDFs into page-tagged blocks and tables (`data/parsed/<doc>.json`), a `[PDF_PAGE_N]`-tagged text rendering, and a parse-quality table. |

Parser features: page numbers come from parser metadata only; per-page text-layer / image check
flags scanned pages (`needs_ocr`, no OCR is run); table finding (ruled tables, with a conservative
whitespace fallback); multi-page table stitching; transposed-table detection; unit detection
(₹ lakh / crore / million / thousand) and Indian-format number parsing.

## Develop

```bash
cd redherring
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest
```

Python 3.12, `uv`, Pydantic v2, pdfplumber + pypdfium2 (both permissive licences; PyMuPDF is
deliberately avoided because it is AGPL).

## Data hygiene

Only public filings are fetched. Source URLs and hashes are recorded. PDFs and parsed outputs are
git-ignored; only `data/sources.toml` and `data/manifest.jsonl` are committed.

## Licence

MIT (see `LICENSE`).

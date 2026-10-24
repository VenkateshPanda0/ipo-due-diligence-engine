# RedHerring

Forensic analysis of Indian IPO offer documents (DRHP / RHP / Prospectus): structured extraction
with page-level citations, a red-flag engine, version diffs, and validation against a labelled
benchmark and post-listing outcomes.

**Status: early.** On filings it had never seen, the first run read about 76% of labelled figures
correctly, twice in a row (6 filings; 2 to 4 wrong values per 41, none invented, the rest
withheld); after fixing what each run exposed the same filings score 99%, which is development
data, not a promise. Labels were written by an AI with no second reader. See `docs/status.md` for
all numbers and known defects, `docs/heldout-run-1.md` and `docs/heldout-run-2.md` for what went
wrong, `docs/roadmap.md` for what is done, and `docs/CHARTER.md` for how the project is run.

> Not investment advice. Automated analysis of public disclosures; verify against the source
> document.

This project lives in the `redherring/` folder of the `ipo-due-diligence-engine` repository and is
independent of the code around it (see `docs/decisions.md` for why, and how to split it out).

## What works

| Command | Does |
|---|---|
| `rh ingest` | Downloads the PDFs in `data/sources.toml` politely (robots.txt, per-host rate limit, size cap, Range-resume of cut-off transfers, `%%EOF` check) and records URL, SHA-256, size, fetch time in `data/manifest.jsonl`. Idempotent. |
| `rh parse` | Parses PDFs (in parallel) into page-tagged blocks and tables with units and assembled column headers; writes `data/parsed/` and a parse-quality table. |
| `rh analyze` | Extracts statement values, issue facts and objects with page citations; re-checks each against the PDF text; runs footing and cross-table consensus; evaluates the red-flag rules in force for the filing's platform and date; writes `data/extracted/` with a per-rule audit. |
| `rh report` | Writes one self-contained HTML page per filing (`data/reports/`): flags with evidence, issue and objects, annual figures in ₹ crore, what could not be checked, every figure linked to its PDF page. |
| `rh diff OLD NEW` | Compares two versions of one offering (draft, updated draft, RHP, prospectus) figure by figure within printed precision, with both pages linked: issue size changes, restated annual figures, flags that appeared or went away. Writes `data/reports/diff_OLD__NEW.html`. Text changes are not compared yet. |
| `rh label-check`, `rh eval` | Validate hand labels (`labels/`) against the PDFs and score the extractor, reporting development and held-out documents separately. |

Red-flag rules live in `src/redherring/flags/rules/*.toml`. A regulatory threshold names the
clause, effective date and the date it was checked against SEBI's consolidated text; a heuristic
threshold says so and cites the literature. Output is diligence flags with evidence, not advice.

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

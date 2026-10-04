# Changelog

All notable project changes are tracked here. Regulation-impacting changes must
include the affected ruleset version and the source regulation or circular.

## [2.0.1] - 2026-10-05

Full code review: correctness fixes, performance work and documentation.

### Fixed — rules (rule_version 2.0.1; see `docs/REGULATIONS.md`)

- Promoter contribution: a shortfall the Reg 14(1) proviso could still cover is no longer
  reported as a failure when contributors are not evidenced.
- Promoter lock-in: under 18 months now fails even when capex status is unknown.
- Public offer tier 6: the ambiguous 1%–2.5% band goes to human review instead of failing.

### Fixed — extraction

- Dates: a day number is no longer taken from the tail of a year ("2026 March, 2025" was
  read as 26 March 2025); month names must start a word.
- Lock-in stated in years ("locked-in for a period of three years") is now recognised.
- Removed a validation rule that wrongly downgraded monetary assets above 5× NTA (DRHPs
  legitimately print ratios above 600%).
- Rule evidence uses canonical field paths (`financials.fiscal_years[FY2024]…`).

### Fixed — backend

- Re-processing a document supersedes its unresolved review items (no duplicates).
- Retention purge no longer deletes a stored PDF still used by an unexpired document.
- Case status: "screened" only while a report exists for the current data version;
  un-archiving restores the state-derived status; archived cases reject field edits.
- Case search treats `%` and `_` literally; fiscal years are ordered by date, not label.
- Merge and field edits no longer mutate the stored (append-only) version in memory.
- Startup validation of `API_KEYS` (role and digest format); `Bearer` is case-insensitive.
- Unknown review IDs return `NOT_FOUND`; the legacy PDF endpoint is rate-limited.

### Fixed — frontend

- Reopening a page preview no longer shows a broken (revoked) image.
- Report export errors are shown; yes/no fields open with their current value; Edit is
  hidden on archived cases; evidence shows readable field labels.

### Performance

- Table header detection: ~20× faster (≈23 s → ≈1.2 s per 500-page DRHP) with
  identical output; only windows that can complete a period are parsed.
- Native text extraction loop and OCR rendering (no PDF re-parse per OCR page).
- Review-item and case listings: batched queries instead of per-row N+1 queries.
- Report listings skip the stored JSON payload; page images are cached in memory.
- The UI polls only while documents are processing; case search is debounced; the
  sidebar count reuses the dashboard query.

### Changed

- `numpy` declared as a dependency (it was only present transitively); removed dead
  code (unused exceptions, constants and helpers) and an unused npm package.
- Pre-commit hooks use the project's own ruff/mypy and no longer block commits to `main`.

## [2.0.0] - 2026-10-04

Audit-driven rebuild. Defects D1–D18 are listed in `docs/audit/BASELINE.md`.

### Regulatory (ruleset 2.0.0)

- Rules re-based on the SEBI ICDR 2018 consolidated text (last amended 2026-03-21), the
  LODR 2015 consolidated text (2026-07-14) and SCRR Rule 19(2)(b) as substituted on
  2026-03-13. See `docs/REGULATIONS.md` for the full change list.
- Fixed: 2009-era citations, the "best 3 of 5" profit test, and a phantom "5×
  net-worth" issue-size rule. Added Reg 5, Reg 6(1)(d) and Reg 6(2), and modelled the
  monetary-asset and promoter-contribution provisos.
- Rule specs, parameters, sources (with SHA-256) and verification status now live in
  versioned JSON. Superseded rulesets refuse to load.
- New verdicts `NOT_APPLICABLE` and `REQUIRES_HUMAN_REVIEW`. New case outcomes
  (`NO_FAILURE_IDENTIFIED`, `SCREENING_FAILURE`, `AWAITING_HUMAN_REVIEW`,
  `INSUFFICIENT_EVIDENCE`, `UNSUPPORTED_SCOPE`). The legacy status is still emitted.
- A FAIL is produced only from reliable evidence. Unreliable inputs lead to review.

### Document intelligence

- Replaced the parser with a local, deterministic multi-stage pipeline: signature and
  limit checks, per-page classification, pdfium text, geometric and vector tables,
  Tesseract OCR fallback with orientation and deskew, lexicon with veto patterns,
  scored candidates, conflict detection, and cross-field validation. There is no LLM.
- Values carry full provenance. Units are never guessed. Ambiguous table rows are
  dropped rather than guessed.
- Embedded JSON in PDFs is no longer trusted (D8).

### Backend

- Cases with immutable data versions, documents with a lifecycle and background
  processing, review items, reports, sign-offs and an audit log, persisted in SQLite
  through SQLAlchemy and Alembic. Audit tables are append-only (enforced by
  triggers).
- `/api/v1` surface added. The legacy endpoints are kept.
- Optional API-key auth with server-side roles (D11), bounded uploads (D12), a single
  error envelope without internal leakage (D13), and a configurable retention period.

### Frontend

- Professional workflow UI: dashboard, cases, documents with page preview, review
  queue, reports with evidence register and exports, rule explorer, and settings.
  Includes runtime response validation, dark mode and responsive layouts.
- Vitest unit tests and Playwright end-to-end tests.

### Benchmark

- 8 public SEBI DRHPs with SHA-256 manifest and answer keys (not human-verified), plus
  `scripts/benchmark_extraction.py`. Results are in `docs/BENCHMARK_RESULTS.md`.

### Removed

- LLM extractor and related settings (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`), the
  PostgreSQL default URL, `sqlmodel`, `structlog`, `factory-boy` and `polyfactory`.

## [1.0.0] - 2026-07-09

### Added

- Canonical `CompanyData` domain model with immutable Pydantic data contracts.
- Deterministic rules engine covering 11 mandatory eligibility rules and 5 advisory due-diligence checks.
- Decision engine with mandatory/advisory rollup, evidence mapping, progress counts, observations, and gap planning.
- Report generator with JSON, text, and HTML outputs.
- FastAPI API for JSON screening, PDF screening, report retrieval, health checks, and rule explorer.
- Human-review API and frontend workflow so machine screening remains advisory and final decisions are recorded by an authorised reviewer.
- Parser boundary for document classification, pdfplumber text extraction, pdfplumber table extraction, OCR fallback hooks, confidence scoring, and self-contained structured label/table extraction.
- Next.js frontend scaffold for upload, report review, and rule exploration.
- Regression tests for deterministic output and import-boundary enforcement.

### Regulation Baseline

- Ruleset version: `1.0.0`.
- Regulatory basis: SEBI ICDR 2018, SEBI LODR 2015, Companies Act 2013, and NSE/BSE listing thresholds represented in `docs/REGULATIONS.md`.

### Known Limitations

- Real-document validation against 5-10 manually checked DRHPs/annual reports remains required before production claims.
- Human-review persistence is in-memory in this local project state; production audit storage remains future work.

## Regulation Change Template

### Changed

- Rule ID:
- Previous requirement:
- New requirement:
- Effective date:
- Source regulation/circular:
- Regression dataset impact:

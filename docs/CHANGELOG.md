# Changelog

All notable project changes are tracked here. Regulation-impacting changes must
include the affected ruleset version and the source regulation or circular.

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

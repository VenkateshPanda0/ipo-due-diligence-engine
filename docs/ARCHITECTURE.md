# Architecture

## System at a glance

```text
 Browser (Next.js 15, pages router)
   │  REST/JSON + Bearer API key (optional)
   ▼
 FastAPI app  ── /api/v1/* (cases, documents, review, screening, reports, rules, system)
   │             /screen/*, /reports/*, /rules/*, /reviews/*, /health (legacy v0, kept)
   │
   ├─ services/      case lifecycle, document lifecycle + worker threads, screening,
   │                 report persistence, human sign-off
   ├─ intelligence/  local PDF pipeline (ingest → pages → tables/OCR → candidates)
   ├─ engine/        deterministic rules engine + decision engine + gap planner
   ├─ rules/         one class per rule, bound to a versioned JSON spec
   ├─ regulatory/    ruleset registry + source register (JSON data)
   ├─ reports/       JSON / text / HTML (Jinja2, autoescaped) formatters
   └─ db/            SQLAlchemy 2.0 models, Alembic migrations, repositories
        │
        ▼
   SQLite (WAL, foreign keys on)        DATA_DIR/documents/<sha256>.pdf
```

Everything runs locally. There is no LLM, cloud service or paid API in any path.
Tesseract is an optional local binary used only for OCR fallback.

## Layering and import boundaries

Enforced by `tests/unit/test_import_boundaries.py`:

| Package | May not import |
|---|---|
| `intelligence` | rules, engine, regulatory, api, services, db |
| `rules`, `engine` | intelligence, api, services, db |
| `regulatory` | rules, engine, intelligence, api, services, db |
| `models` | everything above |

Extraction therefore cannot evaluate a rule, and a rule cannot see a PDF. Both stages
meet only through `CompanyData`.

## Domain model

* `CompanyData` (`models/company_data.py`) is the canonical case data. Every field is
  optional, because missing data has to be representable. Numeric facts are
  `ExtractedValue`s carrying their provenance: document, page, original text and unit,
  period, statement basis, method (`manual`, `native_text`, `table_*`, `ocr`,
  `calculated`, `human_corrected`), confidence, field status, conflicts and notes.
  `ExtractedValue.is_reliable()` decides whether a value may support a PASS or FAIL.
* `RuleResult` carries the rule ID and version, legal category, verification status,
  source URL, verdict, applicability, calculation steps, evidence, missing inputs,
  review reasons, remediation and limitations.
* `IPOReport` carries the case outcome, the legacy status, the ruleset and engine
  versions, the SHA-256 of the input, document and extraction-run IDs, unresolved
  issues, limitations and `regulatory_validation_confirmed`.

## Case lifecycle and data flow

```text
create case (route: Reg 6(1) | Reg 6(2) | SME → unsupported)
   │
   ├── enter / edit facts ───────────────► case_data_versions v1, v2 … (immutable)
   │
   ├── upload PDF ─► ingest checks ─► documents row (uploaded)
   │                     │
   │               worker thread: extracting → completed | awaiting_review | failed
   │                     │   extraction_runs + field_results (every field decision)
   │                     ▼
   │               merge policy: fill only empty / machine-sourced fields;
   │               never overwrite a human value; open review_items for
   │               anything not high-confidence ─► new data version
   │
   ├── review items: confirm | correct | reject | request more evidence
   │      (reason required to correct / reject) ─► review_item_events + new data version
   │
   ├── run screening ─► engine on the current version ─► reports (immutable)
   │
   └── reviewer sign-off ─► human_reviews + human_review_events (append-only)
```

* **Document states**: `uploaded → extracting → completed | awaiting_review | failed`
  (also `cancelled`), enforced by a transition table in `services/documents.py`. A
  failed or cancelled document can be retried. An `awaiting_review` document becomes
  `completed` once its review items are resolved. A content deletion (manual or by
  retention) keeps the metadata, hash and audit trail. Startup moves jobs left in `extracting` by a crash back to `failed` with
  a clear message.
* **Idempotency**: a second upload with the same SHA-256 to the same case returns the
  existing document.
* **Reports** record the case data version, ruleset version, input hash, documents and
  extraction runs used. Re-running on unchanged inputs gives an identical result,
  apart from the timestamp and IDs (`tests/regression/test_reproducibility.py`).

## Persistence

SQLite through SQLAlchemy 2.0. The schema is created by Alembic at startup
(`db/migrations/versions/0001_initial_schema.py`). Tables:

`cases`, `case_data_versions`, `documents`, `extraction_runs`, `field_results`,
`review_items`, `review_item_events`, `reports`, `human_reviews`,
`human_review_events`, `audit_events`.

`case_data_versions`, `review_item_events`, `human_review_events` and `audit_events`
are **append-only**. Database triggers reject `UPDATE` and `DELETE` on them. Reports are
immutable at the repository level, which offers no update path; a re-screen creates a
new report. The audit log records actor, action, entity and timestamp. It never records
document contents or secrets.

## Decision engine

1. `RuleRegistry(version)` loads the ruleset JSON, rejects superseded versions, and
   binds every rule class to its spec, failing on any ID or version mismatch.
2. Each rule decides applicability for the case route. If it applies, it gathers
   inputs through `Inputs`, which records missing paths, evidence and unreliable
   values, and returns PASS / FAIL / INCONCLUSIVE / REQUIRES_HUMAN_REVIEW /
   NOT_APPLICABLE. A FAIL needs reliable evidence.
3. `DecisionEngine` rolls mandatory results up into the outcome, with precedence
   `UNSUPPORTED_SCOPE > SCREENING_FAILURE > AWAITING_HUMAN_REVIEW >
   INSUFFICIENT_EVIDENCE > NO_FAILURE_IDENTIFIED`, and maps that onto the legacy
   `IPOStatus`. Advisory results are reported but never change the outcome.
4. `GapPlanner` turns each non-pass result into a remediation item. It marks
   professional review as required when a result is a legal judgement rather than a
   number.

A rule exception is caught per rule. That rule becomes `REQUIRES_HUMAN_REVIEW` with a
generic message, and no traceback reaches the client.

## Security

* **Auth** is optional. With no keys configured, a local single-user principal is used.
  `API_KEYS="user|role|key-or-sha256=hex,…"` maps keys to roles server-side
  (viewer < analyst < reviewer < admin), and keys are compared in constant time.
  Client-supplied role headers are ignored (defect D11).
* **Uploads**: reads are chunked and bounded, the file type is checked by byte
  signature, there are page and size limits, a per-user rate limit, and encrypted or
  unrepairable PDFs are rejected. Embedded JSON or JavaScript in a PDF is never trusted
  or executed (D8). Stored names are content hashes.
* **Errors**: one envelope `{error:{code,message,request_id,details}}`, with
  allow-listed details only. 500s are generic (D13). `X-Request-ID` is validated and
  echoed.
* **Logging**: JSON logs with request IDs. Document text and financial values are not
  logged.
* **HTML reports**: Jinja2 autoescape plus a restrictive CSP header. The frontend sets
  its security headers in `next.config.js`.
* **Retention**: `RETAIN_DOCUMENTS` and `RETENTION_DAYS`. Expired PDFs are purged at
  startup, and metadata, hashes and audit history remain.

## Frontend

Next.js 15 with React 19, TanStack Query, and zod validation of every API response
(contract mismatches are surfaced, not ignored), with strict TypeScript. Pages:
dashboard, cases (list, new, detail with facts, documents, review, screenings and
history tabs), document detail (field outcomes, per-page processing, run details, page
preview), review queue, reports (list and detail with outcome, mandatory assessment,
evidence register, unresolved issues, limitations, exports and sign-off), rule
explorer, and settings / system health. The frontend never computes a regulatory
outcome. It only displays what the backend returns.

## Configuration

All settings come from environment variables (see `.env.example`), and every setting
has a safe local default. `REGULATORY_VALIDATION_CONFIRMED` defaults to `false`, and
reports show that value.

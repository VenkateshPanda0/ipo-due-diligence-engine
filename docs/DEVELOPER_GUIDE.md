# Developer guide

## Prerequisites

* Python 3.12
* Node.js 20+ and npm
* Optional: the Tesseract 5 binary with `eng` and `osd` data, for OCR of scanned pages
  (`apt install tesseract-ocr`). Without it, scanned pages are reported as unreadable.

There are no API keys, cloud accounts or databases to provision.

## Setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env            # optional; every setting has a local default
(cd frontend && npm ci)
```

## Run locally

```bash
# backend: http://127.0.0.1:8000  (OpenAPI docs at /docs outside production)
cd backend && ../.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# frontend: http://localhost:3000
cd frontend && NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

The SQLite database and stored PDFs go to `./data` (relative to where the backend
starts) unless `DATABASE_URL` / `DATA_DIR` say otherwise. Migrations run at startup.

To try authentication, set for example
`API_KEYS="alice|reviewer|sha256=<hex of key>,bob|analyst|bob-key"`, then enter the key
under **Settings** in the UI. The key is kept in session storage only.

Docker: `docker build -t ipo-dd . && docker run -p 8000:8000 -v ipo-data:/data ipo-dd`
runs the backend as a non-root user with OCR available.

## Tests

| Suite | Command | Notes |
|---|---|---|
| Backend (all) | `cd backend && ../.venv/bin/pytest -q tests/` | Unit, integration, regression. Uses a temp `DATA_DIR`. |
| Backend coverage | `make coverage` | |
| Lint / format / types | `.venv/bin/ruff check backend && .venv/bin/ruff format --check backend && .venv/bin/mypy backend/app` | |
| Frontend unit | `cd frontend && npm run typecheck && npm test` | Vitest + Testing Library |
| End-to-end | start the backend and frontend as above, then `cd frontend && npm run e2e` | Playwright. Uses the pre-installed Chromium if `PLAYWRIGHT_BROWSERS_PATH` is set. Generates a synthetic DRHP through the backend fixture factory. |
| Extraction benchmark | `.venv/bin/python scripts/benchmark_extraction.py --download --run` | Real DRHPs, takes minutes. See BENCHMARK.md. |

Synthetic PDF fixtures (`backend/tests/fixtures/pdf_factory.py`) cover layouts and
failure modes: scanned, rotated, split tables, encrypted and damaged files. They are
not evidence of real-world accuracy; the benchmark is.

## Code map

```text
backend/app/
  api/            FastAPI app wiring, middleware (errors, request IDs), routers (v1 + legacy)
  core/           settings, security (principals, roles), logging, constants
  db/             SQLAlchemy models, Alembic migrations, repositories
  engine/         rules engine, decision engine, gap planner
  intelligence/   PDF pipeline (see DOCUMENT_INTELLIGENCE.md)
  models/         Pydantic domain models (CompanyData, ExtractedValue, RuleResult, IPOReport…)
  regulatory/     ruleset + source register (JSON) and loader
  reports/        report generator and JSON / text / HTML formatters
  rules/          mandatory/ and advisory/ rule classes
  services/       cases, documents, screening, reports, human review, file store
frontend/src/
  lib/            API client (zod-validated), schemas, formatting, form validation
  components/     ui primitives, layout, case, report components
  pages/          Next.js routes
benchmark/        DRHP manifest + answer keys (PDFs downloaded on demand)
scripts/          benchmark runner
```

## Conventions

* **Eligibility logic lives only in `rules/`.** A rule takes `CompanyData` and returns a
  `RuleResult`. It reads its thresholds from its JSON spec, never from literals.
* **Never FAIL on unreliable evidence.** Use `Inputs` in `rules/base_rule.py`, which
  turns unreliable values into `REQUIRES_HUMAN_REVIEW`.
* **Never guess.** Extraction leaves a field empty, or opens a review item, rather than
  assuming a unit, period or basis.
* **Import boundaries** are enforced by `tests/unit/test_import_boundaries.py`.
* **Errors** raise subclasses of `models.exceptions.DomainError`. The middleware
  maps them onto the error envelope. Only allow-listed `public_fields` reach clients.
* **Logging**: structured JSON. Never log document text, extracted values, keys or
  tokens.
* Formatting is `ruff format` with a line length of 100. `mypy --strict` runs on
  `backend/app`, and TypeScript runs in strict mode.

## Adding or changing a rule

1. Create a new ruleset version: copy `rulesets/<current>.json` to a new version, mark
   the old one `superseded`, and update `CURRENT_RULESET_VERSION`.
2. Edit or add the rule spec (provision, parameters, decision procedure, limitations,
   verification status, sources). Add any new sources to `sources.json` with the
   retrieval date and SHA-256.
3. Implement or adjust the rule class and register it in `rules/registry.py`.
4. Add tests for pass, fail, boundary, missing input, unreliable input and
   not-applicable route.
5. Update `docs/REGULATIONS.md` and `docs/CHANGELOG.md`.

## Adding an extraction label

Add the positive and negative patterns in `intelligence/lexicon.py`. Then add a matching
case **and** a trap case to `tests/unit/intelligence/test_numbers_periods_lexicon.py`,
run the development benchmark split, and report any regression honestly. Never change
an answer key to make a score go up.

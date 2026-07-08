# IPO Due Diligence Engine

> An explainable, deterministic regulatory decision engine with AI-assisted document intelligence.

---

## Status

The IPO Due Diligence Engine is a working technical prototype for first-pass IPO
screening. It is not legal, investment, or regulatory advice and is not yet a
production-certified compliance product.

Readiness summary:

- Works locally through API, frontend, tests, reports, and demo scripts.
- Encodes a tested subset of SEBI/NSE/BSE/Companies Act checks.
- Requires legal/regulatory validation before production use.
- Does not claim 99.99% accuracy or complete current-regulation coverage.

See [docs/REGULATORY_VALIDATION.md](docs/REGULATORY_VALIDATION.md).

## What This Is

The IPO Due Diligence Engine evaluates a private or SME company's readiness for
an Initial Public Offering against an implemented subset of SEBI ICDR, NSE, and
BSE listing requirements. It automates part of the first-pass screening work a
merchant banker's analyst team does manually when deciding whether a company is
worth pursuing as an IPO client.

**Core principle:** Eligibility logic is always deterministic and rule-based — never left to an LLM.
AI is used only for extracting financial data from PDFs. This split is the architectural foundation
of the entire system.

---

## Architecture

```
Upload DRHP / financials (PDF)
        ↓
Document Intelligence Layer  →  AI extracts raw values; attaches confidence scores
        ↓
CompanyData (canonical schema)  →  validated, immutable, typed domain object
        ↓
Rules Engine  →  pure functions: f(CompanyData) → RuleResult
        ↓
Decision Engine  →  mandatory/advisory rollup → IPOStatus
        ↓
Evidence Mapper + Gap Planner
        ↓
Report Generator  →  verdict + regulation citations + remediation timeline
        ↓
API / Frontend
        ↓
Human Review  →  authorised reviewer records the final decision
```

**The dependency boundary:** the Rules Engine never imports parser code. It only knows
`CompanyData`. The same rules run on data from PDFs, manual JSON, or API integrations.

---

## Project Structure

```
backend/
  app/
    models/      ← CompanyData, RuleResult, IPOReport, all domain types (no logic)
    rules/       ← SEBI/NSE/BSE regulation implementations (no parser imports)
    engine/      ← RulesEngine, DecisionEngine, EvidenceMapper, GapPlanner
    parser/      ← PDF extraction, OCR, AI extractor (no rule logic)
    reports/     ← Report generation and formatting
    api/         ← FastAPI routers and schemas
    services/    ← Orchestration layer
  tests/
    unit/        ← Rule and engine tests (100% branch coverage required)
    integration/ ← API and service tests
    regression/  ← Golden dataset tests
docs/
  SPEC.md        ← Product specification
  ARCHITECTURE.md← Full system design
  DEVELOPER_GUIDE.md ← Engineering conventions
  ROADMAP.md     ← Milestone task breakdown
```

---

## Quickstart

```bash
# 1. Clone and install
git clone https://github.com/example/ipo-due-diligence-engine
cd ipo-due-diligence-engine
pip install -e ".[dev]"

# 2. Copy environment variables
cp .env.example .env
# Edit .env with your API keys and database URL

# 3. Run tests
make test

# 4. Lint and type-check
make lint
make typecheck

# 5. Start the development server
make run
```

## Docker

```bash
docker build -t ipo-due-diligence-engine .
docker run --rm -p 8000:8000 ipo-due-diligence-engine
```

---

## Running Tests

```bash
# All tests
make test

# Unit tests only (no external dependencies)
make test-unit

# With coverage report
make coverage

# Regression suite (golden datasets)
make test-regression
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| No blended readiness score | A single number obscures which regulation failed — the only information that matters |
| AI only for extraction | LLMs hallucinate; rule engines do not. Wrong extraction → human review flag. Wrong eligibility → silent client harm |
| Human final decision | The engine prepares evidence and a machine status; it never replaces an authorised reviewer |
| `CompanyData` is the separation boundary | Rules know nothing about PDFs; parsers know nothing about regulations |
| Every rule is unit-tested | The rules are the product; untested rule branches are potential silent eligibility errors |
| Reports tagged with `RulesetVersion` | Same `CompanyData` + same version = byte-identical output forever |

See [docs/SPEC.md](docs/SPEC.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full
technical specification.

---

## Documentation

- [Product Specification](docs/SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Developer Guide](docs/DEVELOPER_GUIDE.md)
- [Regulations Reference](docs/REGULATIONS.md)
- [Regulatory Validation Gate](docs/REGULATORY_VALIDATION.md)
- [Human Review Workflow](docs/HUMAN_REVIEW_WORKFLOW.md)
- [Document Intelligence](docs/DOCUMENT_INTELLIGENCE.md)
- [Changelog](docs/CHANGELOG.md)

---

## License

MIT

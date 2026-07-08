# IPO Due Diligence Engine — Developer Guide

> **Status:** Living document. Every architectural decision made in this
> codebase must be traceable to a section here. If you are about to do
> something this guide does not address, add the section first, get it
> reviewed, then write the code.

---

## Table of Contents

1. [Project Philosophy](#1-project-philosophy)
2. [Engineering Principles](#2-engineering-principles)
3. [Dependency Rules](#3-dependency-rules)
4. [Folder Responsibilities](#4-folder-responsibilities)
5. [Python Coding Standards](#5-python-coding-standards)
6. [FastAPI Standards](#6-fastapi-standards)
7. [SQLModel Standards](#7-sqlmodel-standards)
8. [Logging](#8-logging)
9. [Error Handling](#9-error-handling)
10. [Testing Philosophy](#10-testing-philosophy)
11. [Documentation Standards](#11-documentation-standards)
12. [Git Standards](#12-git-standards)
13. [Security Guidelines](#13-security-guidelines)

---

## 1. Project Philosophy

### 1.1 Core Goals

This project exists to answer one question on behalf of a merchant banker's
analyst team: *"Is this company eligible for an IPO under current SEBI/NSE/BSE
regulations, and if not, exactly why and when might it be?"*

The system must answer that question with:

- **Precision.** The eligibility determination is binary and rule-derived.
  There is no grey zone produced by weighted averages or model confidence.
- **Traceability.** Every verdict must cite the regulation it checks, the
  value it found, and the document page it extracted that value from.
- **Reproducibility.** Given the same `CompanyData` and the same
  `RulesetVersion`, the engine must produce byte-for-byte identical output
  every time it runs, forever.
- **Honesty about uncertainty.** Where extraction is uncertain (low OCR
  confidence, ambiguous table structure), the system says so explicitly and
  requires human confirmation. It never silently substitutes an assumption.

These goals are listed in priority order. When they conflict — and they
will — precision and traceability win.

### 1.2 Design Philosophy

**Trust is the product.** A screening tool that produces a confident wrong
answer is more dangerous than one that produces no answer. Every design
decision must be evaluated against this standard: does this change make the
system easier or harder to trust?

Consequences of that standard:

- Eligibility logic is never delegated to an LLM. LLMs hallucinate; rule
  engines do not.
- Blended "readiness scores" are forbidden. A single number obscures which
  specific regulation failed and by how much, which is the only information
  that matters.
- AI is used exclusively where its failure mode is recoverable: extracting
  text and flagging items for human review. A wrong extraction triggers a
  "manual confirmation required" flag. A wrong eligibility determination
  would silently mislead a client.

**Simplicity is a constraint, not a goal.** The system should be as simple as
it can be while satisfying the above. Adding infrastructure, abstraction, or
features that do not serve precision, traceability, or reproducibility is
waste. See §6a of the spec for the explicit list of things to resist.

### 1.3 Deterministic-First Architecture

Every module is classified as either **deterministic** or **probabilistic**
before any code is written.

| Layer | Classification | Rationale |
|---|---|---|
| Rules Engine | Deterministic | Encodes regulations as executable predicates |
| Decision Engine | Deterministic | Rolls up rule outcomes by mandatory/advisory status |
| Evidence Mapper | Deterministic | Maps verdicts to their source citations |
| Report Generator | Deterministic | Renders a report from structured data |
| Document Parser | Probabilistic | OCR and table extraction are inherently uncertain |
| AI Extraction | Probabilistic | LLM output is non-deterministic by nature |

Probabilistic outputs **must never flow directly into deterministic modules.**
They must be converted into validated, typed `CompanyData` first. The
conversion step is where uncertainty is surfaced, confidence levels are
attached, and human confirmation is requested if confidence is below
threshold.

This is not an implementation detail. It is the central architectural
invariant of the entire system.

### 1.4 Explainability

Every output the system produces must be self-explaining. A user who reads a
report without access to any other documentation must be able to understand:

- What the system checked and why.
- What value it found.
- Where it found that value.
- What the regulation actually requires.
- Whether the check passed or failed, and by what margin.

This is enforced structurally: the `RuleResult` type carries the regulation
reference, the required value, the actual value, the source citation, and the
verdict together. There is no path through the system that produces a verdict
without also producing its explanation.

### 1.5 Evidence Traceability

Evidence traceability is a first-class feature, not a logging concern.

Every numeric value in `CompanyData` must carry provenance metadata:

```python
class ExtractedValue(BaseModel):
    value: Decimal
    source_document: str        # e.g. "DRHP_FY2025.pdf"
    page_number: int | None
    extraction_method: ExtractionMethod   # PDF_TABLE | OCR | MANUAL
    confidence: ConfidenceLevel           # HIGH | MEDIUM | LOW
    confirmed_by_human: bool
```

A value with `confidence=LOW` and `confirmed_by_human=False` blocks report
generation unless the report is explicitly marked as a draft. This is not
configurable at runtime. It is enforced by the Decision Engine.

---

## 2. Engineering Principles

### 2.1 Separation of Concerns

The architecture is layered. Each layer has exactly one job and knows nothing
about the layers above it.

```
Document Intelligence  →  extracts raw text, tables, values from PDFs
CompanyData            →  the single, validated data contract between layers
Rules Engine           →  applies regulations to CompanyData
Decision Engine        →  rolls up rule results into a verdict
Evidence Mapper        →  attaches source citations to every verdict
Report Generator       →  renders the structured result as a human-readable report
```

A module that does two things from different layers is wrong and must be
refactored. If you find yourself importing a parser into a rule, or a rule
into a parser, stop and read §3.

### 2.2 SOLID Principles

**Single Responsibility.** Each class does one thing. `OperatingProfitRule`
evaluates operating profit. `EvidenceMapper` maps evidence. Neither does both.

**Open/Closed.** The Rules Engine is open to extension (new rules are added
as new classes) and closed to modification (adding a new rule never requires
changing existing rule code or the engine's evaluation loop).

**Liskov Substitution.** All rules implement `BaseRule`. The engine accepts a
`list[BaseRule]` and does not branch on rule type. If a rule cannot be
evaluated without the engine knowing its type, the abstraction is wrong.

**Interface Segregation.** `BaseRule` exposes only `evaluate(company:
CompanyData) -> RuleResult`. It does not expose parsing methods, database
methods, or reporting methods. Keep interfaces minimal.

**Dependency Inversion.** High-level modules (Decision Engine) depend on
abstractions (`BaseRule`, `RuleResult`), not on concrete rule implementations.
Concrete rules are injected at configuration time, not imported directly by
the engine.

### 2.3 Composition over Inheritance

Prefer composing behaviour from small, single-purpose pieces over building
deep class hierarchies.

Acceptable:

```python
class NetWorthRule(BaseRule):
    def evaluate(self, company: CompanyData) -> RuleResult:
        checker = ThresholdChecker(threshold=ICDR_NET_WORTH_THRESHOLD)
        return checker.evaluate(company.net_worth, self.metadata)
```

Not acceptable:

```python
class NetWorthRule(ThresholdRule):          # layered inheritance
    class Meta(ThresholdRule.Meta):         # meta-class stacking
        threshold = ICDR_NET_WORTH_THRESHOLD
```

The second form creates coupling through the inheritance chain that makes
individual rules harder to test and harder to reason about in isolation.

### 2.4 Explicit Dependencies

No global state. No module-level singletons. No `get_db()` called implicitly
inside a rule.

All dependencies are passed in explicitly at construction time or as function
arguments. This makes every unit testable in isolation without mocking module
globals.

```python
# Correct
class DecisionEngine:
    def __init__(self, rules: list[BaseRule], ruleset_version: RulesetVersion) -> None:
        self.rules = rules
        self.ruleset_version = ruleset_version

# Wrong
class DecisionEngine:
    rules = load_rules_from_registry()   # global side effect at import time
```

### 2.5 Immutable Data Where Appropriate

`CompanyData` and all `RuleResult` objects are immutable after construction.
Use `model_config = ConfigDict(frozen=True)` on Pydantic models that represent
domain facts.

The purpose: once a `RuleResult` is produced by the Rules Engine, nothing
downstream may alter it. The Evidence Mapper annotates results; it does not
modify them. The Report Generator renders results; it does not modify them.
Immutability enforces this structurally rather than by convention.

Mutable state is permitted only in the persistence layer (SQLModel database
models) and in intermediate parsing state (where values are assembled before
being frozen into `CompanyData`).

### 2.6 Type Safety

This codebase targets Python 3.12+. All code uses full type annotations.
`mypy --strict` must pass with zero errors on every commit. There are no
`# type: ignore` comments without an accompanying explanation of why the
suppression is safe.

Use `Decimal` for all financial figures, never `float`. Floating-point
rounding errors in financial computations produce wrong eligibility answers,
which is the one failure mode this project cannot tolerate.

```python
from decimal import Decimal

operating_profit: Decimal = Decimal("18400000")   # ₹1.84 Cr in paise
```

---

## 3. Dependency Rules

These rules are enforced at architecture review and, where tooling allows, via
import linters. Violations block merge.

### Rule 1: The Rules Engine MUST NOT import parser code.

The Rules Engine knows nothing about PDFs, OCR engines, extraction libraries,
or any document format. It receives a `CompanyData` object. That is all it
receives. If you find a parser import inside `backend/app/rules/`, you have
found a bug in the architecture.

### Rule 2: The Parser MUST NOT contain business logic.

The parser's job is to extract values from documents and express uncertainty
about those values. It does not know what the SEBI threshold for operating
profit is. It does not decide whether a value passes or fails any check. It
does not format output. It produces `ExtractedValue` objects and hands them
to the service layer that assembles `CompanyData`.

### Rule 3: The Decision Engine MUST NOT implement regulations.

The Decision Engine aggregates `RuleResult` objects produced by the Rules
Engine. It applies mandatory/advisory classification to those results and
derives an overall verdict. It does not know what operating profit is,
what the ICDR thresholds are, or what any specific regulation says. That
knowledge lives entirely in the Rules Engine.

### Rule 4: AI may extract information but MUST NEVER determine eligibility.

LLM API calls are permitted only in `backend/app/parser/` and
`backend/app/services/extraction_service.py`. They produce text, tables,
flagged items, and confidence assessments. They do not produce `RuleResult`
objects, verdicts, or eligibility determinations. Any code that passes a
`RuleResult` to an LLM or uses an LLM output directly in an eligibility
calculation is wrong.

### Rule 5: `CompanyData` is the ONLY accepted input to the Rules Engine.

No rule's `evaluate()` method may accept parameters beyond `company:
CompanyData`. Rules do not accept database sessions, HTTP clients, file
handles, or any other external dependency. This guarantees that the Rules
Engine is pure: given the same `CompanyData`, it always produces the same
`RuleResult`. Always.

### Rule 6: Reports must be reproducible from the same `CompanyData` and `RulesetVersion`.

Given `company_data: CompanyData` and `ruleset_version: RulesetVersion`, the
report generator must always produce identical output. This means:

- No timestamps in rule evaluation logic.
- No random or non-deterministic operations anywhere in the deterministic
  layers.
- `RulesetVersion` is a parameter, not read from an environment variable
  inside the engine.

Report reproducibility is verified by the regression test suite (§10.3).

### Rule 7: Modules depend inward toward the domain.

The dependency direction is always inward:

```
API → Services → Engine → Rules → Models
                         ↑
               Parser → Services → Models
```

`Models` (the domain) depends on nothing inside this codebase. `Rules` depends
only on `Models`. `Engine` depends on `Rules` and `Models`. `Services` depends
on `Engine`, `Parser`, and `Models`. `API` depends on `Services`. Nothing
depends outward. Nothing in the domain layer imports from `api/`, `parser/`,
or `services/`.

---

## 4. Folder Responsibilities

Every folder has exactly one job. Adding code that does not belong in a
folder's stated responsibility is an architectural violation.

### `backend/app/models/`

**Responsibility:** Domain types and data contracts. No logic, no I/O, no
dependencies outside standard library and Pydantic/SQLModel.

Contains:
- `company_data.py` — the `CompanyData` Pydantic model and all its nested
  types (`ExtractedValue`, `FinancialHistory`, `PromoterRecord`, etc.)
- `rule_result.py` — `RuleResult`, `RuleMetadata`, `RulesetVersion`, `Verdict`
- `report.py` — `IPOReport`, `MandatoryCheckSection`, `AdvisoryCheckSection`,
  `GapPlan`, `Observation`
- `enums.py` — `ConfidenceLevel`, `ExtractionMethod`, `RuleCategory`,
  `IPOStatus`
- `exceptions.py` — domain exception types (§9.1)

Does NOT contain: database models, API schemas, rule logic, parser logic.

### `backend/app/rules/`

**Responsibility:** SEBI/NSE/BSE regulation logic, encoded as deterministic
Python predicates. One file per regulation cluster. One class per rule.

Contains:
- `base.py` — `BaseRule` abstract class with the `evaluate()` contract
- `mandatory/` — one module per regulation category
  - `profitability.py` — operating profit, EBITDA, PAT rules (ICDR Reg 6)
  - `net_worth.py` — net worth eligibility rules
  - `track_record.py` — years-in-operation and operational continuity rules
  - `float_requirements.py` — minimum public shareholding rules
  - `promoter.py` — promoter lock-in, debarment history rules
- `advisory/` — non-blocking checks
  - `governance.py` — board composition, audit committee independence
  - `related_party.py` — RPT volume thresholds and flagging
  - `auditor.py` — auditor changes, qualifications
  - `litigation.py` — material litigation flagging
- `registry.py` — assembles the canonical rule list for a given
  `RulesetVersion`; this is the only place that knows all the rules

Does NOT contain: parser imports, database imports, API imports, AI calls.

### `backend/app/engine/`

**Responsibility:** Orchestrate rule evaluation and produce a structured
decision. Does not implement any individual regulation.

Contains:
- `rules_engine.py` — iterates rules, calls `evaluate(company)`, collects
  `RuleResult` objects
- `decision_engine.py` — separates mandatory from advisory results, derives
  `IPOStatus`, counts satisfied requirements
- `evidence_mapper.py` — attaches source citations and regulation references
  to each `RuleResult`
- `gap_planner.py` — for failed mandatory rules with quantifiable thresholds,
  computes gap size and projects earliest eligible fiscal year

Does NOT contain: parser imports, AI calls, rule implementations, database
write logic.

### `backend/app/parser/`

**Responsibility:** Extract structured data from raw documents (PDFs, scanned
images). Produce `ExtractedValue` objects with provenance and confidence.
Explicitly probabilistic — all outputs carry uncertainty metadata.

Contains:
- `pdf_parser.py` — pdfplumber-based text and table extraction
- `ocr_engine.py` — fallback OCR for scanned documents
- `table_detector.py` — Camelot-based structured table extraction
- `ai_extractor.py` — LLM API calls for governance section summarization,
  litigation item identification, related-party flagging; the only file in
  the codebase permitted to make AI API calls
- `confidence.py` — confidence scoring logic: cross-validation between
  extraction methods, heuristics for table structure quality
- `document_classifier.py` — classifies an uploaded document as DRHP,
  annual report, audited financials, etc.

Does NOT contain: rule logic, eligibility thresholds, decision logic, API
route handlers.

### `backend/app/reports/`

**Responsibility:** Render a completed `IPOReport` into human-readable output.
Pure transformation — no computation, no eligibility logic.

Contains:
- `generator.py` — assembles the `IPOReport` model from engine outputs
- `formatters/`
  - `json_formatter.py` — JSON serialization (primary machine-readable output)
  - `text_formatter.py` — plain-text report for CLI and debugging
  - `html_formatter.py` — structured HTML for frontend consumption (optional)
- `templates/` — Jinja2 templates if HTML output is used

Does NOT contain: rule logic, parsing logic, database writes.

### `backend/app/api/`

**Responsibility:** HTTP interface. Validation of incoming requests, routing to
services, serialization of responses. Contains no business logic.

Contains:
- `routers/`
  - `screening.py` — `/screen` endpoints: JSON input and PDF upload
  - `reports.py` — `/reports/{id}` retrieval endpoints
  - `rules.py` — `/rules` introspection endpoint (Rule Explorer feature)
- `schemas/`
  - `requests.py` — Pydantic request body models
  - `responses.py` — Pydantic response models (never return domain models
    directly to clients)
- `dependencies.py` — FastAPI dependency functions (database sessions,
  service instances)
- `middleware.py` — correlation ID injection, request logging

Does NOT contain: rule logic, parser logic, direct database queries.

### `backend/app/services/`

**Responsibility:** Coordinate between the parser, engine, and persistence
layers to fulfil a single application use case. Services are the only layer
that touches multiple lower-level modules in the same operation.

Contains:
- `screening_service.py` — orchestrates a full screening run: receive input
  → assemble `CompanyData` → run engines → persist → return `IPOReport`
- `extraction_service.py` — coordinates document parsing and AI extraction to
  produce `CompanyData` from a raw PDF; the only layer that calls
  `parser/ai_extractor.py`
- `report_service.py` — fetches persisted reports, applies formatting

Does NOT contain: rule implementations, raw SQL queries, HTTP logic.

### `backend/tests/`

**Responsibility:** Test suite. Organised to mirror the module structure.

```
tests/
  unit/
    rules/          # one test file per rule file; covers all rule predicates
    engine/         # tests for engine orchestration logic
    parser/         # tests for extraction and confidence scoring
    reports/        # tests for formatters and report assembly
  integration/
    api/            # FastAPI TestClient tests for all routes
    services/       # tests that cross service + engine + parser boundaries
  regression/
    companies/      # one directory per test company with fixture data
      company_a/
        input.json          # CompanyData as JSON
        expected_report.json  # canonical expected output for this ruleset version
    test_regression.py    # parametrized test that asserts output matches fixture
  conftest.py
  fixtures/
```

### `frontend/`

**Responsibility (stretch goal):** React/Next.js application consuming the
FastAPI backend. Contains no business logic — all eligibility and evidence
logic lives in the backend.

```
frontend/
  src/
    components/
      MandatoryChecks/
      AdvisoryChecks/
      GapPlanner/
      EvidencePanel/
      RuleExplorer/
    pages/
    api/          # typed client wrappers around backend endpoints
    types/        # TypeScript types mirroring backend response schemas
```

### `docs/`

**Responsibility:** Project documentation. Source of truth for design
decisions that are not expressed in code.

```
docs/
  SPEC.md               # Product specification (authoritative, do not edit without review)
  DEVELOPER_GUIDE.md    # This document
  ARCHITECTURE.md       # System diagram, data flow, module interaction diagram
  REGULATIONS.md        # Human-readable index of all encoded regulations with citations
  CHANGELOG.md          # Ruleset version changelog (see §5 of spec)
  adr/                  # Architecture Decision Records
    001-no-blended-score.md
    002-ai-extraction-only.md
    003-manual-ruleset-versioning.md
```

---

## 5. Python Coding Standards

### 5.1 Type Hints

All function signatures carry full type annotations. No `Any` without an
explanatory comment. All class attributes are annotated.

```python
# Correct
def evaluate(self, company: CompanyData) -> RuleResult:
    ...

# Wrong
def evaluate(self, company):
    ...
```

Run `mypy --strict backend/` as part of every pre-commit check. CI blocks
merge on mypy failures.

### 5.2 Docstrings

Every public module, class, and function has a docstring. Private helpers
(prefixed `_`) are documented when their behaviour is not obvious from the
name.

Format: Google-style docstrings.

```python
def evaluate(self, company: CompanyData) -> RuleResult:
    """Evaluate operating profit eligibility against ICDR Regulation 6(1)(a).

    Args:
        company: The structured company data model. Must have at least three
            years of audited financial history for this rule to produce a
            definitive verdict.

    Returns:
        A RuleResult with verdict PASS if average operating profit across
        the three most recent audited years meets or exceeds the threshold
        defined in ICDR_OP_THRESHOLD, FAIL otherwise, or INCONCLUSIVE if
        insufficient financial history is available.

    Raises:
        InsufficientDataError: If company.financial_history is empty.
    """
```

### 5.3 Formatting

This project uses **Ruff** for both linting and formatting.

Configuration lives in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "TCH"]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

`ruff format` and `ruff check` are both run as pre-commit hooks. CI blocks
merge on any ruff failure. Do not configure your editor to use Black; Black
and Ruff formatters produce subtly different output.

### 5.4 Naming Conventions

| Construct | Convention | Example |
|---|---|---|
| Modules | `snake_case` | `profitability.py` |
| Classes | `PascalCase` | `OperatingProfitRule` |
| Functions / methods | `snake_case` | `evaluate_rule()` |
| Constants | `UPPER_SNAKE_CASE` | `ICDR_OP_THRESHOLD` |
| Type aliases | `PascalCase` | `RuleList = list[BaseRule]` |
| Private members | `_leading_underscore` | `_compute_average()` |
| Test functions | `test_<what>_<condition>` | `test_operating_profit_below_threshold()` |

Do not use abbreviations unless they are universally understood in the domain
(`SEBI`, `DRHP`, `ICDR`, `OCR` are acceptable; `op_prof` is not).

### 5.5 Imports

Imports are organised in three groups, separated by blank lines, in this
order:

1. Standard library
2. Third-party packages
3. Internal modules

```python
import json
from decimal import Decimal
from typing import Final

import pydantic
from fastapi import Depends

from app.models.company_data import CompanyData
from app.models.rule_result import RuleResult
```

Relative imports are not used. All internal imports use the full `app.`
package path.

`__all__` is defined in every `__init__.py` that exposes a public surface.

### 5.6 Dataclasses vs Pydantic vs SQLModel

| Use case | Type |
|---|---|
| Domain models passed between layers | `pydantic.BaseModel` with `frozen=True` |
| Database-persisted records | `sqlmodel.SQLModel` |
| Simple value objects with no validation | `@dataclass(frozen=True)` |
| Mutable intermediate state in parsers | `@dataclass` (mutable) |

Never use plain `dict` to pass structured data between layers. Typed models
make the contract explicit and catch errors at construction time rather than
at access time.

---

## 6. FastAPI Standards

### 6.1 Routers

Each domain area has its own router file in `backend/app/api/routers/`. No
routes are defined in `main.py` other than mounting the routers.

```python
# backend/app/api/routers/screening.py

router = APIRouter(prefix="/screen", tags=["Screening"])

@router.post("/json", response_model=IPOReportResponse, status_code=200)
async def screen_from_json(
    payload: ScreeningRequest,
    service: ScreeningService = Depends(get_screening_service),
) -> IPOReportResponse:
    """Screen a company from a structured JSON payload.

    Use this endpoint when company data is already structured. For PDF
    input, use POST /screen/pdf instead.
    """
    ...
```

All routes have:
- an explicit `response_model`
- a docstring that will appear in the OpenAPI documentation
- an explicit HTTP status code

### 6.2 Dependency Injection

All service and database dependencies are injected via `Depends()`. No service
is instantiated directly inside a route handler.

```python
# backend/app/api/dependencies.py

def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

def get_screening_service(db: Session = Depends(get_db)) -> ScreeningService:
    return ScreeningService(db=db, rules=build_rule_registry())
```

The `build_rule_registry()` function assembles the canonical rule list for
the current `RulesetVersion`. It is called once per request so that the
ruleset version in effect at request time is always the current one.

### 6.3 Response Models

API response schemas live in `backend/app/api/schemas/responses.py` and are
distinct from domain models. Never return a domain model or SQLModel instance
directly from a route handler. The response schema is the contract with
external consumers; the domain model is an internal concern.

```python
class IPOReportResponse(BaseModel):
    report_id: UUID
    ruleset_version: str
    company_name: str
    status: IPOStatus
    requirements_satisfied: int
    requirements_total: int
    mandatory_checks: list[MandatoryCheckResponse]
    advisory_checks: list[AdvisoryCheckResponse]
    gap_plans: list[GapPlanResponse]
    observations: list[str]
    generated_at: datetime
```

### 6.4 Error Handling

All expected error conditions are handled via FastAPI exception handlers
registered in `main.py`. Route handlers do not contain `try/except` blocks
for domain errors — they let domain exceptions propagate to the handler.

```python
# backend/app/main.py

@app.exception_handler(InsufficientDataError)
async def insufficient_data_handler(
    request: Request, exc: InsufficientDataError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "INSUFFICIENT_DATA", "detail": str(exc), "fields": exc.fields},
    )
```

HTTP 500 responses must never leak stack traces to clients. All unhandled
exceptions are caught by a generic handler that logs the full traceback
internally and returns a sanitised `{"error": "INTERNAL_ERROR"}` response.

---

## 7. SQLModel Standards

### 7.1 Naming

Database table names use `snake_case` plural nouns. Column names use
`snake_case`. Foreign key columns are named `<referenced_table_singular>_id`.

```python
class ScreeningRun(SQLModel, table=True):
    __tablename__ = "screening_runs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_name: str = Field(index=True)
    ruleset_version: str
    status: IPOStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    company_data_id: UUID = Field(foreign_key="company_data_snapshots.id")
```

### 7.2 Relationships

Define relationships explicitly using `Relationship`. Do not rely on ORM lazy
loading in API handlers — use `selectinload` or `joinedload` in service
methods to avoid N+1 queries.

### 7.3 Migrations

All schema changes are managed via **Alembic**. Migration scripts live in
`backend/alembic/versions/`. Rules:

- Never modify an existing migration file after it has been merged to `main`.
- Every migration is reversible: `downgrade()` must undo `upgrade()` cleanly.
- Migration files are named `{revision}_{short_description}.py`.
- Run `alembic upgrade head` as part of application startup in development.
  In production, migrations run as a separate step before the app container
  starts.

### 7.4 Versioning

`ScreeningRun` records store the `ruleset_version` string at the time of the
run. This allows any report to be reproduced by loading the same
`CompanyData` snapshot and re-running the Rules Engine at the stored ruleset
version. The current `RulesetVersion` is defined as a constant in
`backend/app/rules/registry.py` and is bumped manually when regulations
change (see `docs/CHANGELOG.md`).

---

## 8. Logging

### 8.1 Structured Logging

All log output is structured JSON, emitted to stdout. Do not use print
statements. Do not use unstructured string formatting in log calls.

Use `structlog` configured with JSON rendering in production and
console rendering in development (detected via `APP_ENV` environment variable).

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info(
    "rule_evaluated",
    rule_id="operating_profit",
    regulation="ICDR_6_1_a",
    verdict="PASS",
    company_name=company.name,
    correlation_id=ctx.correlation_id,
)
```

Every log event has a short `snake_case` event name as the first positional
argument. Additional context is passed as keyword arguments.

### 8.2 Log Levels

| Level | Use |
|---|---|
| `DEBUG` | Detailed extraction steps, intermediate values during parsing |
| `INFO` | Rule evaluations, screening run start/end, report generation |
| `WARNING` | Low-confidence extractions, missing optional fields, deprecated usage |
| `ERROR` | Extraction failure on a mandatory field, failed rule due to bad data |
| `CRITICAL` | Rules Engine invariant violation, database unavailable at startup |

Do not log at `ERROR` for user input errors (missing fields, invalid format).
Those are `WARNING` or `INFO`. Reserve `ERROR` for conditions the system
cannot handle without human attention.

### 8.3 Correlation IDs

Every incoming HTTP request is assigned a `correlation_id` (UUID) by the
correlation middleware in `backend/app/api/middleware.py`. This ID is:

- Returned in the response header `X-Correlation-ID`.
- Bound to the structlog context for the duration of the request.
- Included in every log event emitted during that request.
- Stored on the `ScreeningRun` database record.

This means any log line from any layer can be traced back to the originating
request.

---

## 9. Error Handling

### 9.1 Domain Exceptions

Domain exceptions live in `backend/app/models/exceptions.py`. They represent
conditions the domain understands and can describe.

```python
class IPOEngineError(Exception):
    """Base class for all domain exceptions."""

class InsufficientDataError(IPOEngineError):
    """Raised when CompanyData lacks required fields for a rule evaluation."""
    def __init__(self, rule_id: str, missing_fields: list[str]) -> None:
        self.rule_id = rule_id
        self.fields = missing_fields
        super().__init__(f"Rule '{rule_id}' requires: {missing_fields}")

class ExtractionFailedError(IPOEngineError):
    """Raised when a mandatory field cannot be extracted from the document."""

class RulesetVersionError(IPOEngineError):
    """Raised when a requested ruleset version is not available."""

class ReproducibilityError(IPOEngineError):
    """Raised when a report cannot be reproduced from stored data."""
```

### 9.2 Validation Exceptions

Pydantic validation errors from `CompanyData` construction are caught in
`extraction_service.py` and converted to structured `ExtractionFailedError`
or `InsufficientDataError` before propagating further. The Rules Engine
never receives a `CompanyData` object that failed validation.

### 9.3 API Exceptions

HTTP-specific error responses are not raised as exceptions inside service or
engine code. Services raise domain exceptions. The FastAPI exception handlers
in `main.py` translate domain exceptions to HTTP responses. This keeps
services testable without an HTTP context.

The error response shape is consistent across all endpoints:

```json
{
  "error": "INSUFFICIENT_DATA",
  "detail": "Rule 'operating_profit' requires: ['financial_history']",
  "correlation_id": "3f2a1b4c-..."
}
```

---

## 10. Testing Philosophy

### 10.1 Unit Tests for Every Rule

Every rule in `backend/app/rules/` has a corresponding test file in
`backend/tests/unit/rules/` with the same name.

Each test file covers:

1. **Happy path — PASS.** The company data satisfies the rule's threshold.
2. **Happy path — FAIL.** The company data falls below the threshold.
3. **Boundary condition — exact threshold.** The value equals the threshold
   exactly. Document whether the rule is `>=` or `>` and test accordingly.
4. **INCONCLUSIVE conditions.** Mandatory fields are absent or have
   `confidence=LOW` without human confirmation.
5. **Edge cases specific to the regulation.** For example, the operating
   profit rule averages three years — test what happens with exactly one year
   of history, two years, and zero years.

```python
# tests/unit/rules/mandatory/test_profitability.py

class TestOperatingProfitRule:
    def test_pass_when_average_meets_threshold(self, three_year_financials):
        company = CompanyDataFactory.build(financial_history=three_year_financials)
        result = OperatingProfitRule().evaluate(company)
        assert result.verdict == Verdict.PASS

    def test_fail_when_average_below_threshold(self, low_profit_financials):
        company = CompanyDataFactory.build(financial_history=low_profit_financials)
        result = OperatingProfitRule().evaluate(company)
        assert result.verdict == Verdict.FAIL

    def test_boundary_exactly_at_threshold(self, threshold_financials):
        company = CompanyDataFactory.build(financial_history=threshold_financials)
        result = OperatingProfitRule().evaluate(company)
        assert result.verdict == Verdict.PASS  # ≥ threshold passes

    def test_inconclusive_with_single_year_of_history(self, single_year_financials):
        company = CompanyDataFactory.build(financial_history=single_year_financials)
        result = OperatingProfitRule().evaluate(company)
        assert result.verdict == Verdict.INCONCLUSIVE

    def test_raises_on_empty_financial_history(self):
        company = CompanyDataFactory.build(financial_history=[])
        with pytest.raises(InsufficientDataError):
            OperatingProfitRule().evaluate(company)
```

Use `polyfactory` or a project-local `CompanyDataFactory` to build test
fixtures. Never use `dict` literals to construct `CompanyData` in tests —
if the model changes, typed factories break loudly at the construction site,
not silently at a later assertion.

### 10.2 Edge Cases

Edge cases are not optional. The rules encode regulations that real companies
rely on. Missed edge cases produce wrong eligibility verdicts. Specifically
required for every rule:

- Exact threshold values (boundary conditions).
- Missing optional fields that the rule accesses.
- Values at `Decimal("0")`.
- Negative values where the domain permits them (e.g. negative net worth is
  a meaningful signal, not an error).
- Multi-year rules with fewer years than expected.

### 10.3 Regression Tests

The regression suite lives in `backend/tests/regression/`. It is the
authoritative guard against rule regressions.

Structure:

```
regression/
  companies/
    acme_corp/
      input.json             # CompanyData serialized to JSON
      expected_fy2025_v2026_03.json   # expected IPOReport for this ruleset version
    greenfield_sme/
      input.json
      expected_fy2025_v2026_03.json
  test_regression.py
```

`test_regression.py` is parametrized: for each company fixture, it loads
`input.json`, runs the full engine at the specified `RulesetVersion`, and
asserts the output matches `expected_*.json` exactly.

**A rule change is not accepted unless the regression suite passes with the
updated expected outputs checked in.** Changing expected outputs is
legitimate (the regulation changed); changing expected outputs to make a
broken rule appear to pass is not. Pull requests that update expected
regression outputs must include a reference to the regulation amendment that
justifies the change.

### 10.4 Test Coverage

Minimum coverage requirements, enforced by `pytest-cov` in CI:

| Module | Minimum coverage |
|---|---|
| `backend/app/rules/` | 100% |
| `backend/app/engine/` | 95% |
| `backend/app/models/` | 90% |
| `backend/app/parser/` | 80% |
| `backend/app/api/` | 85% |

The `rules/` coverage requirement is 100%. This is not aspirational. The
rules are the product. Untested rule branches are potential silent eligibility
errors.

---

## 11. Documentation Standards

### 11.1 Module-Level Docstrings

Every Python module begins with a docstring that states:

- What the module contains.
- What it does NOT contain (to enforce architectural boundaries).
- Which regulation(s) it encodes, if applicable.

```python
"""
backend/app/rules/mandatory/profitability.py

Implements SEBI ICDR Chapter II eligibility rules related to profitability.
Specifically encodes Regulation 6(1)(a) (operating profit track record) and
Regulation 6(1)(b) (net tangible assets).

This module MUST NOT import from:
  - app.parser (no document parsing logic)
  - app.api (no HTTP logic)
  - Any third-party AI or LLM library

All thresholds are sourced from SEBI ICDR Regulations 2018 as amended up to
the ruleset version pinned in app.rules.registry.CURRENT_RULESET_VERSION.
"""
```

### 11.2 Public API Examples

Every public function and class in the `rules/` and `engine/` modules
includes a usage example in the docstring.

```python
class OperatingProfitRule(BaseRule):
    """Check average operating profit against ICDR Reg 6(1)(a).

    Example:
        >>> from app.models.company_data import CompanyData
        >>> from app.rules.mandatory.profitability import OperatingProfitRule
        >>> company = CompanyData(...)
        >>> result = OperatingProfitRule().evaluate(company)
        >>> result.verdict
        <Verdict.PASS: 'PASS'>
        >>> result.actual_value
        Decimal('18400000')
    """
```

### 11.3 Architecture Decision Records

Significant architectural decisions are documented in `docs/adr/` as
short markdown files. A decision is "significant" if a reasonable engineer
might question it. The format is:

```markdown
# ADR-001: No blended readiness score

**Status:** Accepted  
**Date:** 2026-04

## Context
...

## Decision
...

## Consequences
...
```

ADRs are never deleted. If a decision is reversed, the original ADR is marked
`Superseded by ADR-NNN` and a new ADR explains the reversal and its
reasoning.

### 11.4 `REGULATIONS.md`

`docs/REGULATIONS.md` is a human-readable index of every regulation encoded
in the Rules Engine. For each regulation it lists: the rule ID, the
regulatory citation, the requirement in plain English, the threshold value,
and the implementing class. This document is updated whenever a rule is
added, changed, or removed.

---

## 12. Git Standards

### 12.1 Commit Message Format

Commits follow Conventional Commits:

```
<type>(<scope>): <short description>

[optional body]

[optional footer: BREAKING CHANGE, Closes #issue]
```

Types: `feat`, `fix`, `rule`, `test`, `refactor`, `docs`, `chore`.

Use `rule` for any commit that adds, modifies, or removes a regulation
encoding. This makes it easy to audit the history of eligibility logic.

```
rule(profitability): update ICDR 6(1)(a) threshold per 2026 amendment

Previous threshold: ₹15 Cr average operating profit
New threshold: ₹20 Cr average operating profit

Source: SEBI ICDR Amendment Regulations 2026, Circular No. SEBI/HO/CFD/XXX
See docs/CHANGELOG.md for full entry.

Closes #47
```

Short descriptions are imperative mood, lowercase, no trailing period, max
72 characters.

### 12.2 Branch Naming

```
feat/<short-description>       # new feature
fix/<short-description>        # bug fix
rule/<regulation-id>           # new or updated rule
test/<what-is-being-tested>    # test additions only
refactor/<what>                # refactor with no behaviour change
docs/<what>                    # documentation only
```

Examples:

```
rule/icdr-6-1-a-profitability
feat/gap-to-ipo-planner
fix/evidence-mapper-missing-page-number
```

Branches are short-lived. Nothing stays in a branch for more than a week
without a pull request open.

### 12.3 Pull Request Checklist

Every pull request must satisfy all of the following before merge:

- [ ] `mypy --strict` passes with zero errors.
- [ ] `ruff check` and `ruff format --check` pass.
- [ ] All new rules have unit tests at 100% branch coverage.
- [ ] Regression suite passes. If expected outputs changed, the PR description
      links to the regulation change that justifies the update.
- [ ] New public functions and classes have docstrings with examples.
- [ ] If a regulation was encoded or changed, `docs/REGULATIONS.md` is
      updated and `docs/CHANGELOG.md` has an entry.
- [ ] If an architectural boundary was crossed intentionally (rare), the
      relevant section of this guide has been updated and reviewed.
- [ ] No `print()` statements in non-test code.
- [ ] No `TODO` comments merged without a linked issue.

---

## 13. Security Guidelines

### 13.1 Input Validation

All input entering the system — whether from the API, from a PDF, or from
AI extraction — is validated through Pydantic models before it reaches any
business logic. Validation is not optional and is not the responsibility of
the calling code; the model constructor is the boundary.

Financial values are validated for plausible ranges. A revenue figure of
`Decimal("-999999999999")` extracted from a PDF is an extraction error, not
a legitimate company value. Range validators on `ExtractedValue` catch these
before `CompanyData` is constructed.

PDF uploads are validated before parsing:

- MIME type must be `application/pdf`.
- File size must not exceed the configured `MAX_UPLOAD_SIZE_MB`.
- The PDF is parsed in a subprocess with a timeout to prevent denial-of-service
  via maliciously crafted files.

### 13.2 Secrets Management

No secrets appear in source code, configuration files, or git history.
Secrets are read exclusively from environment variables, loaded via
`pydantic-settings` into a `Settings` model at startup.

```python
class Settings(BaseSettings):
    anthropic_api_key: SecretStr
    openai_api_key: SecretStr | None = None
    database_url: SecretStr
    app_env: Literal["development", "production"] = "development"
```

`SecretStr` ensures that API keys are not accidentally logged or included in
repr output. Call `.get_secret_value()` only at the point of use inside
`ai_extractor.py`.

In local development, secrets are loaded from a `.env` file that is
`.gitignore`d. The repository contains a `.env.example` with placeholder
values and documentation for each variable.

### 13.3 Prompt Injection Considerations

The AI extraction layer (`backend/app/parser/ai_extractor.py`) accepts
document content as input to LLM prompts. Document content is untrusted. A
malicious actor could embed instructions in a DRHP PDF designed to manipulate
the LLM's extraction output.

Mitigations in place:

- System prompts instruct the model to extract only and to ignore any
  instructions embedded in the document itself.
- LLM outputs are validated against strict Pydantic schemas before use.
  A response that does not match the expected structure is treated as an
  extraction failure, not acted upon.
- LLM outputs **never flow into the Rules Engine directly.** They are converted
  to `ExtractedValue` objects, which are then manually validated and
  assembled into `CompanyData`. Even a fully compromised LLM output cannot
  change an eligibility verdict — it can only trigger a `confidence=LOW`
  extraction that requires human confirmation.

This layered approach means that the security boundary for eligibility
correctness is `CompanyData` construction, not LLM prompt engineering.
Prompt engineering is the first line of defence; `CompanyData` validation
and the deterministic Rules Engine are the last.

### 13.4 Safe AI Usage

AI API calls are made only in `backend/app/parser/ai_extractor.py`. No
other module imports an AI client or makes an AI API call. This is an
architectural rule, not a convention.

AI responses that take longer than the configured `AI_EXTRACTION_TIMEOUT_S`
are cancelled and treated as extraction failures. The system does not hang
waiting for an LLM response.

AI API keys are rotated on a schedule. Failed API calls are retried with
exponential backoff up to a maximum of three attempts; after that, the
extraction fails with an `ExtractionFailedError` and the field is marked
as requiring manual entry.

---

*This document is maintained by the Principal Architect. Proposed changes
require a pull request with a review from at least one senior engineer.
Architectural decisions that contradict this guide must be documented in
`docs/adr/` before the code is merged.*

*Last updated: July 2026 — Ruleset version 2026-03*

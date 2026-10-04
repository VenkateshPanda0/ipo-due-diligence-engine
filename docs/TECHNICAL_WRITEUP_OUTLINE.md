# Technical Write-Up Outline

> **Historical document (pre-2.0.0).** Kept for context. Where it conflicts with the current
> design — LLM extraction, PostgreSQL, `Eligible`/`Not Eligible` wording, ICDR 2009 numbering —
> the current documents win: README.md, ARCHITECTURE.md, REGULATIONS.md and ADR 0005–0007.

## Thesis

Regulatory screening software should optimize for traceability and
reproducibility, not for a polished but opaque score.

## Translating Regulations to Code

- Each regulation is represented as a `BaseRule` subclass.
- Rule metadata carries regulation, section, clause, category, and description.
- Unit tests cover pass, fail, boundary, and inconclusive cases.

## Deterministic and Probabilistic Boundary

- Parser modules may be uncertain.
- `CompanyData` is the boundary between extraction and eligibility.
- Rules never import parser code and never call AI.

## Evidence Model

- `ExtractedValue` keeps value, source document, page, method, confidence, and
  human-confirmation state together.
- `EvidenceMapper` attaches citations to `RuleResult` without mutating the
  original result.

## Decision Model

- Mandatory failures produce `NOT_ELIGIBLE`.
- Inconclusive mandatory checks without failures produce `NEEDS_REVIEW`.
- Advisory failures are reported but do not block eligibility.

## Testing Strategy

- Unit tests for every rule.
- Integration tests for service and API workflows.
- Regression tests for reproducibility and architectural import boundaries.
- Coverage report for broad module-level confidence.

## Tradeoffs

- In-memory storage keeps the demo simple but is not production persistence.
- Local deterministic parsing keeps the project self-contained; production OCR
  and table extraction can be added behind the parser interfaces.
- Frontend is intentionally thin and delegates all business decisions to the API.

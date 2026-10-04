# ADR-0001: Deterministic Rules Engine

**Status:** Accepted (extraction approach refined by ADR-0005: no AI/LLM extraction)
**Date:** 2026-07-09

## Context

IPO eligibility is a regulatory determination. A wrong answer can mislead a
company or banker even if the interface appears confident. Document extraction
may be probabilistic, but eligibility cannot be.

## Decision

All eligibility logic lives in deterministic rule classes that accept only
`CompanyData` and return `RuleResult`. Parser and AI modules may extract facts,
but they never produce verdicts or eligibility decisions.

## Consequences

- The same `CompanyData` and ruleset produce reproducible rule outcomes.
- Extraction uncertainty is represented as confidence and human-confirmation metadata.
- Parser modules and rule modules are separated by import-boundary tests.

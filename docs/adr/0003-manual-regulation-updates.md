# ADR-0003: Manual Regulation Updates

**Status:** Accepted
**Date:** 2026-07-09

## Context

Automated regulation diffing sounds attractive but can misread amendments,
transition dates, circular applicability, and exchange-specific thresholds.

## Decision

Regulation changes are reviewed and implemented manually through versioned
rulesets, changelog entries, tests, and updated regulation references.

## Consequences

- Regulatory interpretation remains a human-reviewed engineering change.
- Regression outputs change only with a documented source.
- Release history remains auditable.

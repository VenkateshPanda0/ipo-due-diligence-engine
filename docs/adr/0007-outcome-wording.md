# ADR-0007: Screening outcomes, not eligibility verdicts

**Status:** Accepted
**Date:** 2026-10-04

## Context

The 1.0.0 status `ELIGIBLE` read as a legal conclusion. It was produced even when
inputs were unverified machine extractions.

## Decision

Case outcomes are `NO_FAILURE_IDENTIFIED`, `SCREENING_FAILURE`,
`AWAITING_HUMAN_REVIEW`, `INSUFFICIENT_EVIDENCE` and `UNSUPPORTED_SCOPE`. They are
described as, for example, "no failure identified within the supported screening
scope". A FAIL requires reliable evidence. Unreliable evidence gives
`REQUIRES_HUMAN_REVIEW`. The legacy `IPOStatus` is still emitted for compatibility, and
every report lists its limitations and `regulatory_validation_confirmed`.

## Consequences

- The UI and exports never say a company "is eligible".
- More cases end in review states. That is intended: the engine narrows the work, and
  people decide.

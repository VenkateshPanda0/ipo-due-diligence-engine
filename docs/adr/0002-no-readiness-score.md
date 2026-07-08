# ADR-0002: No Blended Readiness Score

**Status:** Accepted
**Date:** 2026-07-09

## Context

A single readiness score can hide the fact that one mandatory regulation failed.
For IPO screening, the important output is the exact failed requirement and the
gap to compliance.

## Decision

The system reports pass/fail/inconclusive counts, mandatory/advisory sections,
and gap analysis instead of a blended score.

## Consequences

- Users see which rules passed, failed, or need review.
- Advisory warnings remain visible without incorrectly blocking eligibility.
- The report avoids false precision from weighted scoring.

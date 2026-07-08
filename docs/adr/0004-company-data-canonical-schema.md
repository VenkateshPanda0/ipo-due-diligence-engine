# ADR-0004: CompanyData as Canonical Schema

**Status:** Accepted
**Date:** 2026-07-09

## Context

The system accepts facts from PDFs, JSON uploads, and potentially manual review.
Rules need one stable contract that preserves evidence and confidence metadata.

## Decision

`CompanyData` is the only input accepted by the rules engine. Values that come
from documents are wrapped in `ExtractedValue` so provenance and confidence stay
attached throughout evaluation.

## Consequences

- Rules are independent of document formats.
- Reports can cite evidence back to source documents and pages.
- Low-confidence extraction becomes an explicit review state instead of a hidden assumption.

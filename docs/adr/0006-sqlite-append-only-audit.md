# ADR-0006: SQLite persistence with append-only audit tables

**Status:** Accepted
**Date:** 2026-10-04

## Context

Reports, reviews and sign-offs were in memory and were lost on restart. The target is
a single-organisation local or demo deployment, so zero-ops setup matters more than
horizontal scale.

## Decision

Use SQLAlchemy 2.0 with Alembic migrations on SQLite (WAL mode, foreign keys on). Case
data is stored as immutable numbered versions. Audit, review-event, sign-off-event and
case-data-version tables are append-only, enforced by `BEFORE UPDATE/DELETE` triggers.
PDFs are stored content-addressed (`<sha256>.pdf`) under `DATA_DIR`.

## Consequences

- Restarts lose nothing. A report can always be traced to the exact data version,
  ruleset and documents behind it.
- Moving to PostgreSQL needs equivalent append-only enforcement (triggers or grants),
  and the in-process worker threads would need a real queue.

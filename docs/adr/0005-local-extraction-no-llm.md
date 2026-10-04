# ADR-0005: Local, deterministic extraction (no LLM)

**Status:** Accepted
**Date:** 2026-10-04

## Context

The 1.0.0 design allowed LLM calls (OpenAI / Anthropic) for field extraction. DRHPs
are often confidential before filing. Sending them to a third party needs specific
authorisation, and LLM outputs are hard to reproduce and to audit. The project brief
requires local operation with no paid API.

## Decision

Extraction is a local, deterministic pipeline (`app/intelligence`): pdfium text,
geometric and vector table reconstruction, Tesseract OCR fallback, a lexicon with veto
patterns, scored candidates and explicit conflict detection. No network call is made
with document content.

## Consequences

- The same PDF and pipeline version produce the same candidates, and every value is
  traceable to a page and its printed text.
- Recall depends on table-layout heuristics. Unsupported layouts give `NOT_FOUND` or
  review items, never invented values.
- If an LLM-assisted extractor is ever added, it must be optional, off by default,
  behind explicit per-deployment consent, and must only *propose* candidates that go
  through the same validation and human review.

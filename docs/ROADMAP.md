# Roadmap

The 1.0.0 milestone plan (LLM extraction, PostgreSQL) was superseded by the 2.0.0
rebuild. See CHANGELOG.md and ADR 0005–0007.

## Done in 2.0.0

* Audit baseline and defect register (D1–D18).
* Ruleset 2.0.0 from primary sources, with a source register and verification
  statuses. Reg 6(1) and Reg 6(2) supported; SME declared unsupported.
* Evidence-first decision semantics: FAIL only on reliable evidence; new outcomes and
  verdicts.
* Cases, documents, review items, reports, sign-offs and an append-only audit log,
  persisted in SQLite with migrations.
* A local multi-stage PDF pipeline with OCR fallback and conflict detection.
* A professional frontend with unit and end-to-end tests.
* A real-DRHP benchmark (8 documents, development/holdout split).

## Next — validation (blocks any production claim)

1. **Human-verify the benchmark answer keys.** A person checks every expected value
   against the PDF, corrects mistakes in a recorded commit, and changes the `reviewer`
   field.
2. **Legal review of ruleset 2.0.0**, following REGULATORY_VALIDATION.md, including the
   six open questions.
3. **Retrieve the primary SCRR and exchange texts.** Move the affected rules out of
   `secondary_sources_only` / `unverified`, or document why that can't be done.
4. **Grow the benchmark** to ≥ 25 DRHPs, including scanned and Reg 6(2) issuers, with
   a larger holdout, and report confidence intervals.

## Next — product

* Basis-consistency check across the Reg 6(1) years (REGULATIONS.md, question 4).
* An SME (Chapter IX) ruleset, as a separate route and separate rules.
* Extraction of Reg 5 declarations and promoter-holding tables, with review.
* A PostgreSQL option with an equivalent append-only guarantee and a real job queue.
* SSO/OIDC and key rotation.
* Report comparison across data versions and ruleset versions.

## Not planned

* A single "IPO readiness score" (ADR 0002).
* LLM-decided outcomes (ADR 0001, 0005).

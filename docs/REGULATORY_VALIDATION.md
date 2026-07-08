# Regulatory Validation Gate

This project is technically runnable, but it must not be represented as a
legally complete SEBI IPO eligibility product until a qualified regulatory
review signs off on the encoded rules.

## Current SEBI Source Check

Source checked: SEBI Legal -> Regulations -> Updated List.

As of the project readiness review on 2026-07-09:

- SEBI ICDR 2018 is listed by SEBI as last amended on 2026-03-21.
- SEBI LODR 2015 is listed by SEBI as last amended on 2026-01-22.

Project status:

- The engine implements 11 mandatory checks and 5 advisory checks.
- The implementation is a useful screening subset, not a clause-by-clause
  encoding of every current ICDR, LODR, Companies Act, NSE, or BSE obligation.
- `REGULATORY_VALIDATION_CONFIRMED=false` by default. Keep it false until a
  legal/regulatory reviewer confirms coverage and interpretation.

## Sign-Off Requirements

Before enabling production use:

1. Compare every implemented rule in `docs/REGULATIONS.md` against the latest
   consolidated SEBI ICDR and LODR texts.
2. Identify missing eligibility paths, SME provisions, disclosure obligations,
   exemptions, transitional provisions, and exchange-specific listing criteria.
3. Add or update rules with tests for pass, fail, boundary, and inconclusive cases.
4. Update `docs/CHANGELOG.md` with source references and effective dates.
5. Regenerate demo outputs and regression fixtures.
6. Set `REGULATORY_VALIDATION_CONFIRMED=true` only after sign-off.

## Accuracy Policy

Do not claim a numeric accuracy percentage until the system has been benchmarked
against a representative, reviewed dataset of real filings and known eligibility
outcomes. Test pass rate is not the same thing as regulatory accuracy.

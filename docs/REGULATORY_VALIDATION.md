# Regulatory validation gate

This project runs, but it must not be presented as a legally complete or legally
reviewed SEBI IPO eligibility product. No qualified securities-law professional has
reviewed the encoded rules.

## Current state (ruleset 2.0.0, 2026-10-04)

* The primary sources were retrieved, with SHA-256 hashes recorded in
  `backend/app/regulatory/data/sources.json`:
  * SEBI ICDR 2018 consolidated text, last amended 21-03-2026.
  * SEBI LODR 2015 consolidated text, last amended 14-07-2026.
* The SCRR Rule 19(2)(b) 2026 substitution could not be retrieved, so the rule rests on
  two secondary summaries (`secondary_sources_only`).
* The BSE and NSE main-board criteria could not be retrieved (HTTP 403), so those rules
  are marked `unverified`.
* There are 13 mandatory and 6 advisory rules for the main-board Reg 6(1) and Reg 6(2)
  routes. SME (Chapter IX) is out of scope and returns `UNSUPPORTED_SCOPE`.
* `REGULATORY_VALIDATION_CONFIRMED=false`, and the ruleset's
  `legal_review.confirmed=false` with an empty `reviewed_rule_ids` list. Every report
  shows this value.

The open legal questions are listed in [REGULATIONS.md](REGULATIONS.md#unresolved-legal-questions).

## Sign-off procedure

1. A qualified reviewer compares each rule in `rulesets/2.0.0.json` (provision,
   parameters, decision procedure, limitations) against the current primary text and
   records any discrepancies.
2. The engineering team fixes the discrepancies in a **new ruleset version**. Published
   versions are never edited in place. Each fix comes with tests for pass, fail,
   boundary, missing and unreliable inputs.
3. The reviewer resolves or accepts each unresolved legal question in writing.
4. The ruleset's `legal_review` block records `confirmed: true`, the reviewed rule IDs
   and a reference to the signed memo. Only then may a deployment set
   `REGULATORY_VALIDATION_CONFIRMED=true` and `REGULATORY_VALIDATION_REFERENCE`.

## Accuracy policy

Do not quote an accuracy percentage as a property of the product. The extraction
benchmark ([BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md)) uses answer keys that have not
been human-verified, and it measures extraction, not eligibility outcomes. A test pass
rate is not regulatory accuracy.

# Regulations reference — ruleset 2.0.0

> **Not legal advice. Not legally reviewed.** Every rule below was transcribed by the
> engineering team from the sources listed. `REGULATORY_VALIDATION_CONFIRMED` stays
> `false` and the ruleset's `legal_review.confirmed` stays `false` until a qualified
> securities-law professional has reviewed and signed off each rule
> (see [REGULATORY_VALIDATION.md](REGULATORY_VALIDATION.md)).

The machine-readable source of truth is
`backend/app/regulatory/data/rulesets/2.0.0.json` (rule specs, parameters, citations,
verification status) and `backend/app/regulatory/data/sources.json` (source register).
The API serves the same data at `GET /api/v1/rules`, `GET /api/v1/rulesets`, and the
frontend renders it in **Rule explorer**. This page is a human-readable index.

## Scope

| Route | Status | Notes |
|---|---|---|
| Main board, ICDR Reg 6(1) (profitability route) | **Supported** | |
| Main board, ICDR Reg 6(2) (QIB / book-built route) | **Supported** | |
| SME platform, ICDR Chapter IX | **Unsupported** | A case on this route returns outcome `UNSUPPORTED_SCOPE`; no rule is evaluated. |
| InvIT / REIT / debt / FPO / rights / QIP | Out of scope | |

## Verification status vocabulary

| Status | Meaning |
|---|---|
| `primary_text_checked` | Rule text compared by an engineer against the retrieved primary instrument (SHA-256 recorded). Not legal review. |
| `secondary_sources_only` | Primary instrument could not be retrieved; content cross-checked against ≥2 independent secondary summaries. |
| `unverified` | Neither the primary source nor two independent secondaries were available, or the rule is an engineering heuristic. |

## Traceability matrix

Mandatory rules can produce `FAIL` and therefore a `SCREENING_FAILURE` outcome.
Advisory rules are shown in reports but never change the outcome.

| Rule ID | Cat. | Legal category | Routes | Provision | Verification | Key parameters | Implementing class |
|---|---|---|---|---|---|---|---|
| `ICDR_REG5_INELIGIBLE_ENTITIES` | M | statutory eligibility | 6(1), 6(2) | ICDR 2018 Reg 5(1)(a)–(d), 5(2) | primary_text_checked | declarations | `rules.mandatory.eligibility.IneligibleEntitiesRule` |
| `NTA_3CR` | M | statutory eligibility | 6(1) | ICDR 2018 Reg 6(1)(a); def. Reg 2(1)(gg) | primary_text_checked | ≥ ₹3 Cr in each of 3 preceding full years | `rules.mandatory.net_tangible_assets.NTARule` |
| `MONETARY_ASSETS_50PCT` | M | statutory eligibility | 6(1) | ICDR 2018 Reg 6(1)(a) + both provisos | primary_text_checked | ≤ 50% of NTA each year; offer-for-sale and deployment-commitment provisos | `rules.mandatory.net_tangible_assets.MonetaryAssetsRule` |
| `AVG_OPERATING_PROFIT_15CR` | M | statutory eligibility | 6(1) | ICDR 2018 Reg 6(1)(b) | primary_text_checked | average ≥ ₹15 Cr over 3 preceding years **and** operating profit in each | `rules.mandatory.profitability.ProfitabilityRule` |
| `NET_WORTH_1CR` | M | statutory eligibility | 6(1) | ICDR 2018 Reg 6(1)(c); def. Reg 2(1)(hh) | primary_text_checked | ≥ ₹1 Cr in each of 3 preceding full years | `rules.mandatory.net_worth.NetWorthRule` |
| `ICDR_REG6_1D_NAME_CHANGE` | M | statutory eligibility | 6(1) | ICDR 2018 Reg 6(1)(d) | primary_text_checked | ≥ 50% revenue from activity indicated by new name | `rules.mandatory.eligibility.NameChangeRule` |
| `ICDR_REG6_2_QIB_ROUTE` | M | statutory eligibility | 6(2) | ICDR 2018 Reg 6(2) | primary_text_checked | book-built; ≥ 75% of net offer to QIBs; refund undertaking | `rules.mandatory.eligibility.QIBRouteRule` |
| `PROMOTER_CONTRIBUTION_20` | M | statutory issue condition | 6(1), 6(2) | ICDR 2018 Reg 14(1) + provisos | primary_text_checked | ≥ 20% post-issue; non-promoter shortfall cover ≤ 10% (a shortfall ≤ 10% without evidence of eligible contributors is *inconclusive*, not a failure) | `rules.mandatory.promoter.PromoterContributionRule` |
| `PROMOTER_LOCK_IN` | M | statutory issue condition | 6(1), 6(2) | ICDR 2018 Reg 16(1)(a) + proviso (w.e.f. 13-08-2021) | primary_text_checked | 18 months; 36 months where proceeds fund capex (< 18 fails under either reading) | `rules.mandatory.promoter.PromoterLockInRule` |
| `PUBLIC_OFFER_MIN` | M | statutory issue condition | 6(1), 6(2) | SCRR 1957 Rule 19(2)(b) as substituted by G.S.R. 184(E), 13-03-2026 | **secondary_sources_only** | six market-cap tiers (25% … 1%); a tier-6 offer between 1% and the 2.5% also cited goes to human review | `rules.mandatory.float_requirements.FloatRequirementsRule` |
| `MIN_POST_ISSUE_CAPITAL` | M | exchange listing criterion | 6(1), 6(2) | BSE / NSE main-board criteria | **unverified** | ≥ ₹10 Cr post-issue paid-up | `rules.mandatory.minimum_capital.MinPostIssueCapitalRule` |
| `MIN_MARKET_CAP` | M | exchange listing criterion | 6(1), 6(2) | BSE main-board criteria | **unverified** | ≥ ₹25 Cr | `rules.mandatory.minimum_capital.MinMarketCapRule` |
| `EXCHANGE_MIN_ISSUE_SIZE` | M | exchange listing criterion | 6(1), 6(2) | BSE main-board criteria | **unverified** | issue ≥ ₹10 Cr | `rules.mandatory.issue_size.IssueSizeRule` |
| `TRACK_RECORD_3Y` | A | exchange listing criterion | 6(1), 6(2) | NSE main-board criteria | **unverified** | ≥ 3 years | `rules.mandatory.track_record.TrackRecordRule` |
| `BOARD_INDEPENDENCE` | A | post-listing obligation | 6(1), 6(2) | LODR 2015 Reg 17(1)(b) | primary_text_checked | ⅓ (non-exec chair) / ½ (otherwise) | `rules.advisory.governance.BoardIndependenceRule` |
| `AUDIT_COMMITTEE` | A | post-listing obligation | 6(1), 6(2) | LODR 2015 Reg 18(1)(a),(b),(d) | primary_text_checked | ≥ 3 members, ⅔ independent, independent chair | `rules.advisory.governance.AuditCommitteeRule` |
| `RPT_DISCLOSURE` | A | diligence indicator | 6(1), 6(2) | heuristic (context: LODR Reg 23) | unverified | RPT/revenue ≤ 0.20 (heuristic) | `rules.advisory.rpt.RPTDisclosureRule` |
| `AUDITOR_QUALIFICATION` | A | diligence indicator | 6(1), 6(2) | heuristic (context: Companies Act s.143) | unverified | — | `rules.advisory.auditor.AuditorQualificationRule` |
| `LITIGATION_RISK` | A | diligence indicator | 6(1), 6(2) | heuristic (context: ICDR Sch. VI) | unverified | exposure/net worth ≤ 0.20 (heuristic) | `rules.advisory.litigation.LitigationRiskRule` |

Class paths are relative to `backend/app/`. `RuleRegistry` refuses to start if a rule
class and the JSON spec disagree on ID or version.

## Route applicability

Rules not applicable to the case's route return `NOT_APPLICABLE` and are listed in the
report, so it is visible that they were deliberately not evaluated.

| Rule | Reg 6(1) | Reg 6(2) | SME (Ch. IX) |
|---|:-:|:-:|:-:|
| Reg 5 ineligible entities | ✓ | ✓ | — |
| NTA / monetary assets / operating profit / net worth / name change | ✓ | N/A | — |
| Reg 6(2) QIB route conditions | N/A | ✓ | — |
| Promoter contribution & lock-in | ✓ | ✓ | — |
| SCRR minimum public shareholding | ✓ | ✓ | — |
| Exchange criteria (capital, market cap, issue size) | ✓ | ✓ | — |
| Advisory rules | ✓ | ✓ | — |

## Decision semantics

| Rule verdict | When |
|---|---|
| `PASS` | All required inputs present and reliable, condition met. |
| `FAIL` | Condition not met **on reliable evidence** (never produced from unverified extraction). |
| `INCONCLUSIVE` | A required input is missing. |
| `REQUIRES_HUMAN_REVIEW` | Inputs present but at least one extracted value is unreliable (needs verification, conflicting candidates, or low confidence) and not yet confirmed by a reviewer. Manual entries and reviewer-confirmed values count as reliable. |
| `NOT_APPLICABLE` | Rule does not apply to the route. |

Case outcome (precedence top to bottom): `UNSUPPORTED_SCOPE` → `SCREENING_FAILURE` →
`AWAITING_HUMAN_REVIEW` → `INSUFFICIENT_EVIDENCE` → `NO_FAILURE_IDENTIFIED`. The legacy
`IPOStatus` (`NOT_ELIGIBLE` / `NEEDS_REVIEW` / `ELIGIBLE`) is still emitted for API
compatibility. `NO_FAILURE_IDENTIFIED` means *"no failure identified within the
supported screening scope"*; it is not a statement that the company is legally eligible.

## Source register

| Source ID | Kind | Retrieved | SHA-256 (prefix) | Used for |
|---|---|---|---|---|
| `SEBI_ICDR_2018_CONSOL_2026_03_21` | primary | 2026-10-04 | `98b627709b65` | Reg 2(1)(gg), 2(1)(hh), 5, 6, 7, 14, 16, 229 |
| `SEBI_LODR_2015_CONSOL_2026_07_14` | primary | 2026-10-04 | `f3c187d46aeb` | Reg 17, 18 |
| `SCRR_1957_R19_2B_GSR184E_2026` | primary — **not retrieved** | — | — | Rule 19(2)(b) tiers |
| `SECONDARY_AZB_SCRR_2026`, `SECONDARY_MONDAQ_SCRR_2026` | secondary | 2026-10-04 | — | corroborate SCRR tiers |
| `BSE_MAINBOARD_IPO_CRITERIA`, `NSE_MAINBOARD_ELIGIBILITY` | primary — **not retrieved (HTTP 403)** | — | — | exchange criteria |
| `ENGINEERING_HEURISTIC` | heuristic | — | — | advisory diligence indicators |

Full SHA-256 digests, URLs and notes are in `sources.json`.

## Change log

### 2.0.0 (active, 2026-10-04)

- Citations corrected from ICDR 2009 numbering (Reg 26/32/36) to ICDR 2018 (Reg 6/14/16).
- `AVG_OPERATING_PROFIT_15CR`: the three preceding years, with operating profit in each
  (was "best 3 of 5", which is the repealed 2009 test).
- `ISSUE_SIZE_5X` removed — no such condition exists in ICDR 2018.
  `EXCHANGE_MIN_ISSUE_SIZE` added (exchange criterion, unverified).
- `PUBLIC_OFFER_MIN` re-based on the six-tier SCRR Rule 19(2)(b) (2026).
- Added `ICDR_REG5_INELIGIBLE_ENTITIES`, `ICDR_REG6_1D_NAME_CHANGE`, `ICDR_REG6_2_QIB_ROUTE`.
- `MONETARY_ASSETS_50PCT`: both provisos modelled.
- `PROMOTER_CONTRIBUTION_20`: Reg 14(1) provisos modelled.
- `TRACK_RECORD_3Y` reclassified as an advisory exchange criterion.
- New verdicts `NOT_APPLICABLE` and `REQUIRES_HUMAN_REVIEW`; new case outcomes.

### 2.0.0 corrections before deployment (rule_version 2.0.1)

- `PROMOTER_CONTRIBUTION_20`: a shortfall of up to 10% with no evidence about eligible
  non-promoter contributors is INCONCLUSIVE (the Reg 14(1) proviso could still cover it);
  a shortfall above 10% still fails.
- `PROMOTER_LOCK_IN`: a committed lock-in shorter than 18 months fails even when it is
  unknown whether the issue funds capex (it is short under either reading).
- `PUBLIC_OFFER_MIN`: in tier 6, an offer meeting the 1% / ₹15,000 Cr conditions but
  below the 2.5% also cited in secondary summaries is REQUIRES_HUMAN_REVIEW, not FAIL —
  the stricter reading is an interpretation.

### 1.0.0 (superseded)

Retained in `rulesets/1.0.0.json` for audit only; the registry refuses to load it.
See `docs/audit/BASELINE.md` (defects D1–D7) for what was wrong with it.

## Unresolved legal questions

These need a securities-law professional; the engine flags rather than decides them.

1. **SCRR Rule 19(2)(b) text.** The 2026 substitution was transcribed from secondary
   summaries. Tier boundaries (inclusive/exclusive) and the transition provisions must be
   confirmed against the e-Gazette.
2. **Exchange criteria.** BSE/NSE pages could not be retrieved; thresholds, and whether
   they apply as conditions or as exchange discretion, are unverified.
3. **"Preceding three full years"** when the latest period is a stub or the company
   changed its financial year — the engine requires three 12-month periods and asks for
   review otherwise.
4. **Restated consolidated vs standalone.** Reg 6(1) refers to restated and consolidated
   figures; DRHPs sometimes present standalone figures for years before a subsidiary
   existed. The extraction pipeline prefers consolidated figures and records the basis of
   every value; the rules do not yet check basis consistency across years.
5. **Reg 6(1)(a) proviso — deployment commitment.** Whether a stated commitment to deploy
   excess monetary assets satisfies the proviso is a judgement call; modelled as a
   user-declared flag (`issue_details.excess_monetary_assets_committed`) that the engine
   takes at face value.
6. **Reg 5 declarations** (wilful defaulter, fraudulent borrower, debarment) are taken
   from user declarations; the engine does not verify them against any register.

## Update process

Regulation updates are manual and versioned (ADR 0003). A change requires a new ruleset
JSON version, source-register entries with retrieval date and hash, unit tests for pass /
fail / boundary / missing / unreliable inputs, a changelog entry here and in
`docs/CHANGELOG.md`, and — before `legal_review.confirmed` may be set — sign-off recorded
in the ruleset's `legal_review` block.

# Regulations Reference

This document indexes the regulatory checks currently encoded in the rules engine.
Mandatory rules can block eligibility. Advisory rules surface due-diligence risks but
do not decide eligibility by themselves.

## Implemented Rules

| Rule ID | Category | Regulation | Requirement | Implementing class |
|---|---|---|---|---|
| `NTA_3CR` | Mandatory | SEBI ICDR 2018, Regulation 26(1), Clause (a) | Net tangible assets must be at least Rs. 3 crore in each of the three preceding full fiscal years. | `app.rules.mandatory.net_tangible_assets.NTARule` |
| `MONETARY_ASSETS_50PCT` | Mandatory | SEBI ICDR 2018, Regulation 26(1), Clause (a) proviso | Monetary assets must not exceed 50% of net tangible assets in each of the three preceding full fiscal years. | `app.rules.mandatory.net_tangible_assets.MonetaryAssetsRule` |
| `AVG_OPERATING_PROFIT_15CR` | Mandatory | SEBI ICDR 2018, Regulation 26(1), Clause (b) | Average pre-tax operating profit must be at least Rs. 15 crore across the best three of the preceding five fiscal years. | `app.rules.mandatory.profitability.ProfitabilityRule` |
| `NET_WORTH_1CR` | Mandatory | SEBI ICDR 2018, Regulation 26(1), Clause (c) | Net worth must be at least Rs. 1 crore in each of the three preceding full fiscal years. | `app.rules.mandatory.net_worth.NetWorthRule` |
| `ISSUE_SIZE_5X` | Mandatory | SEBI ICDR 2018, Regulation 26(2) | Total issue size must not exceed five times pre-issue net worth. | `app.rules.mandatory.issue_size.IssueSizeRule` |
| `TRACK_RECORD_3Y` | Mandatory | SEBI ICDR 2018, Regulation 26(1) | Company must have at least three full fiscal years of operating history. | `app.rules.mandatory.track_record.TrackRecordRule` |
| `PUBLIC_OFFER_MIN` | Mandatory | SEBI ICDR 2018, Regulation 26(5) | Minimum public offer is 25% for expected market cap up to Rs. 1,600 crore and 10% above Rs. 1,600 crore. | `app.rules.mandatory.float_requirements.FloatRequirementsRule` |
| `PROMOTER_CONTRIBUTION_20` | Mandatory | SEBI ICDR 2018, Regulation 32 | Promoters must contribute at least 20% of post-issue paid-up capital. | `app.rules.mandatory.promoter.PromoterContributionRule` |
| `PROMOTER_LOCK_IN` | Mandatory | SEBI ICDR 2018, Regulation 36 | Promoter contribution must be locked in for at least 18 months for standard issues or 36 months for capex issues. | `app.rules.mandatory.promoter.PromoterLockInRule` |
| `MIN_POST_ISSUE_CAPITAL` | Mandatory | NSE/BSE listing requirements | Post-issue paid-up capital must be at least Rs. 10 crore. | `app.rules.mandatory.minimum_capital.MinPostIssueCapitalRule` |
| `MIN_MARKET_CAP` | Mandatory | NSE/BSE listing requirements | Expected market capitalization must be at least Rs. 25 crore. | `app.rules.mandatory.minimum_capital.MinMarketCapRule` |
| `BOARD_INDEPENDENCE` | Advisory | Companies Act 2013 Section 149 / SEBI LODR 2015 Regulation 17 | Board must meet independent-director composition thresholds. | `app.rules.advisory.governance.BoardIndependenceRule` |
| `AUDIT_COMMITTEE` | Advisory | SEBI LODR 2015 Regulation 18 | Audit committee must have at least three directors, at least two-thirds independent members, and an independent chair. | `app.rules.advisory.governance.AuditCommitteeRule` |
| `RPT_DISCLOSURE` | Advisory | SEBI LODR 2015 Regulation 23 | Related-party transactions must be disclosed and certified as arm's length. | `app.rules.advisory.rpt.RPTDisclosureRule` |
| `AUDITOR_QUALIFICATION` | Advisory | Companies Act 2013 Section 143 | Statutory auditor reports should be free of qualifications, modified opinions, and adverse remarks. | `app.rules.advisory.auditor.AuditorQualificationRule` |
| `LITIGATION_RISK` | Advisory | SEBI ICDR 2018, Schedule VI | Material litigation must be disclosed with quantified exposure; criminal cases are high-severity risk flags. | `app.rules.advisory.litigation.LitigationRiskRule` |

## Update Process

Regulation updates are manual and versioned. A rule change must include:

- Code changes in `backend/app/rules/`.
- Unit tests covering pass, fail, boundary, and inconclusive cases.
- Regression expected-output updates when behavior changes.
- A changelog entry explaining the regulatory basis.

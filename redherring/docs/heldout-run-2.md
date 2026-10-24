# Held-out run 2 (2026-10-24): three more unseen filings, after the run-1 fixes

Procedure as in run 1 (D-021): LEAP India RHP (Aug 2026), Shiprocket UDRHP-I (Dec 2025) and Indong
Tea SME prospectus (Sep 2022) were downloaded, their 49 labels were committed (`0ccbe31`), and only
then was the extractor run. A fourth candidate, an NSE Emerge draft prospectus, was dropped because
`nsearchives.nseindia.com` resets connections that identify this tool and the tool will not
disguise itself (the fetcher now stops cleanly on an unreachable robots.txt).

| | held-out set 2, first run |
|---|---|
| labelled fields | 49 (42 present, 7 absent) |
| value accuracy | 32/42 (76%) |
| citation accuracy of correct values | 30/32 (94%) |
| abstained | 8/42 (19%) |
| wrong value | 2/42 (5%) |
| hallucinated (value for an absent field) | 0/7 |

Run 1 scored 76% as well. The fixes made after run 1 were real (every one has a test), but they
bought nothing visible here because the new filings fail in new ways. Generalisation is about 3/4
of fields right, one in twenty wrong, nothing invented, and the remainder withheld.

## Causes

| doc | field | outcome | cause |
|---|---|---|---|
| Shiprocket | offer for sale, total issue | wrong (11,000 and 22,000 vs 12,423.53 and 23,423.53) | the cover table is three columns (fresh, OFS, total) flattened into text; the first amount after "Offer for Sale" is the fresh column's, and the total was then derived from the wrong OFS |
| LEAP India | monitoring agency | abstained | "has appointed X to monitor the utilisation" has no "monitoring agency" next to "appointed" |
| Indong Tea | fresh issue | abstained | SME cover row "Fresh Issue ₹1,301.04 Lakhs | Nil | ₹1,301.04 Lakhs" has no "aggregating" |
| Indong Tea | monitoring agency | abstained | "has not appointed any monitoring agency" was not a recognised phrasing |
| Indong Tea | total income, PBT, PAT FY2022 | abstained | wording "Total Revenue", "Profit/Loss before Taxation", "Net Profit /Loss after adjustments" |
| Indong Tea | cash from operations FY2022 | abstained | the cash-flow statement carries no unit caption, so its figures are never converted or compared |

## Fixes (so set 2 is now development data too)

Cover amounts are collected from every mention and resolved so that fresh + OFS = total (weighted
by how often each figure is printed); "aggregating up to X comprising a fresh issue" is the total; the
SME type row is read; two monitoring-agency phrasings added; SME label wording added; a
captionless statement now takes the unit of sibling statements within two pages that name exactly
the same period dates, only if they agree and never from a table that itself borrowed (parser v11,
recorded in `unit_inherited_from`). A third held-out set is needed before quoting a new
generalisation figure.

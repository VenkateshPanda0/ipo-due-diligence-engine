# Status

Latest first. Every number below was printed by `rh parse` / `rh analyze` on the six documents in
`data/sources.toml`; nothing is estimated. There are still **no hand-labelled ground truth
labels**, so none of this is an accuracy figure. The checks below are *consistency* checks that
need no labels; they catch many errors but cannot prove a value right.

## 2026-10-24

### What changed since the M0 report
- Parser v8: statement columns anchored by x-position with whole-phrase headers, ruled header bands
  folded into the statement below, continuation tables inheriting headers (recorded in
  `header_inherited_from`), fused ruled cells rebuilt row by row, prose never turned into a table,
  per-row page numbers, parallel page parsing (4 workers; Runwal 259 s to 41 s).
- Extraction: period parsing, statement extractor with label-column detection (SME layouts put a
  serial first), issue sizes / objects / monitoring-agency facts, `verify/` (re-read every cited
  number from the PDF text layer; footing identities; cross-table consensus).
- Rules: TOML specs, engine with per-rule audit, validity windows so a filing is judged by the
  rule versions in force when it was filed; eleven rules, regulatory thresholds taken from SEBI's
  consolidated ICDR text "Amended upto March 21, 2026".

### Parser, six documents (2,458 pages)
| doc | pages | sec | OCR pages | err pages | blocks | raw tbl | logical tbl | multi-pg | % tbl w/ unit |
|---|---|---|---|---|---|---|---|---|---|
| varyaa_prospectus_2024 | 295 | 16.79 | 0 | 0 | 3111 | 196 | 154 | 33 | 33.8 |
| synoptics_dp_2023 | 304 | 15.8 | 1 | 0 | 2584 | 286 | 191 | 52 | 44.5 |
| runwal_rhp_2026 | 611 | 41.47 | 0 | 0 | 6407 | 589 | 489 | 69 | 35.0 |
| moneyview_prospectus_2026 | 537 | 56.19 | 0 | 0 | 5132 | 320 | 306 | 14 | 38.2 |
| paytm_drhp_2021 | 497 | 41.19 | 1 | 0 | 5324 | 349 | 322 | 26 | 33.9 |
| sebi_draft_2010_probe | 214 | 8.49 | 0 | 0 | 2398 | 128 | 116 | 10 | 37.9 |

### Extraction and checks (`rh analyze`)
| doc | values | citation-verified | footing passed | multi-source groups | unanimous | no period | no unit | issue facts verified | rules decisive | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| varyaa_prospectus_2024 | 179 | 179/179 (100%) | 8/8 (100%) | 41 | 39/41 (95%) | 14 | 22 | 3/3 (100%) | 2/4 | 0 |
| synoptics_dp_2023 | 258 | 258/258 (100%) | 8/8 (100%) | 59 | 53/59 (90%) | 36 | 8 | 4/4 (100%) | 2/4 | 0 |
| runwal_rhp_2026 | 415 | 415/415 (100%) | 8/10 (80%) | 51 | 33/51 (65%) | 27 | 52 | 1/1 (100%) | 1/6 | 0 |
| moneyview_prospectus_2026 | 312 | 312/312 (100%) | 20/20 (100%) | 64 | 56/64 (88%) | 109 | 19 | 5/5 (100%) | 3/6 | 0 |
| paytm_drhp_2021 | 234 | 234/234 (100%) | 3/3 (100%) | 37 | 27/37 (73%) | 85 | 38 | 3/3 (100%) | 2/4 | 1 |
| sebi_draft_2010_probe | 148 | 148/148 (100%) | 0/0 | 17 | 8/17 (47%) | 55 | 6 | 1/1 (100%) | 0/6 | 0 |

How to read it:
- **citation-verified**: the printed number is found in the PDF's own text layer on the cited page,
  and in the cited row. 100% is expected by construction for values the table builder located; the
  check exists to catch regressions and any future LLM-sourced value.
- **footing passed**: total income = revenue + other income, PAT = PBT − tax, assets = equity +
  liabilities, per table and period. 47 of 49 pass across the six documents; the two failures are
  Runwal subsidiary tables where the tax sign convention differs.
- **unanimous**: among figures found in at least two tables, how often every reading agrees. Low
  numbers (Runwal 65%, Tanla probe 47%) point at subsidiary/segment tables and definitional
  differences (for example several definitions of "net worth"), not necessarily wrong values.
- **rules decisive**: rules that could be evaluated (flagged or clear) out of those in force for
  the platform and filing date. Most rules still lack inputs, so *zero flags is mostly "not
  enough extracted", not "clean"*. The per-rule reasons are in each `*.financials.json` under
  `rule_audit`.
- The one flag (Paytm: trade receivables +13% vs revenue −15%, FY2020 to FY2021) was checked
  against the source rows on pages 79 and 271.

### Known defects (all measured, none hidden)
- Amounts with misplaced digit-group commas (one example: `10,254,4.96` for `1,02,544.96`) are
  rejected rather than guessed; about 1 in 7,900 comma-numbers.
- "Trade receivables" appears in several balance-sheet sections; where one table shows different
  numbers for the same concept and period, those values are dropped as ambiguous.
- Many tables have no detectable unit (`no unit` column); such values are never converted.
- Runwal has no issue size extracted (its cover is a multi-column table with `[●]`
  placeholders); the 2010 Tanla probe states no price, hence no amount.
- Printed page numbers are found on few SME pages (harmless: citations use the PDF page).
- No scanned document has been tested; OCR is not implemented.
- Eleven rules exist; only those whose inputs were extracted can run (see `rules decisive`).

### Next
Label tooling and an evaluation harness; an LLM layer behind a cost cap (no API key exists in this
environment, so it will be built against a fake provider); segmenter; HTML report; red-team set for
prompt injection; CI step running the offline checks.

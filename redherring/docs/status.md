# Status

Latest first. Every number below was printed by `rh parse`, `rh analyze` or `rh eval` on the nine
filings in `data/sources.toml`; nothing is estimated.

## 2026-10-24 (evening)

### Benchmark (`rh eval`, 182 labelled fields over twelve filings)
| set | docs | fields (present/absent) | value accuracy | citation accuracy | abstained | wrong | hallucinated |
|---|---|---|---|---|---|---|---|
| held-out set 1, **first run** | 3 | 51 (41/10) | 31/41 (76%) | 29/31 | 6 | 4 | 0/10 |
| held-out set 2, **first run** (after set-1 fixes) | 3 | 49 (42/7) | 32/42 (76%) | 30/32 | 8 | 2 | 0/7 |
| all twelve filings now (every one has driven a fix) | 12 | 182 (153/29) | 152/153 (99%) | 143/152 | 1 | 0 | 0/29 |

Read the first two rows, not the last. A filing stops being held out the moment a defect it exposed
is fixed, so the last row is development data and overstates what a new filing will get. Two
independent first runs both gave 76% value accuracy, 2 to 4 wrong values in 41 to 42 and nothing
invented; the fixes between them did not move the number because each new filing fails in new
ways. `docs/heldout-run-1.md` and `docs/heldout-run-2.md` list every miss and its cause. Labels
were written by the maintainer, an AI, with no second reader (`labels/README.md`).

### Rules
Eleven rules. Regulatory ones now start on 10 Nov 2018 (ICDR 2018) unless a later amendment date
applies, so a 2005 draft is not judged by 2018 law. The cash-flow rule is not applied to lenders or
real-estate developers (sector detected from the front of the document). Flags currently raised
across nine filings: Paytm trade receivables vs revenue (FY2020 to FY2021, checked against source
rows) and the Tanla 2005 draft's operating cash flow below profit in two of three years.

### Parser, nine documents (parser v10)
| doc | pages | sec | OCR pages | err pages | % OCR | blocks | raw tbl | logical tbl | multi-pg | transposed? | % tbl w/ unit | printed pg # |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| varyaa_prospectus_2024 | 295 | 20.97 | 0 | 0 | 0.0 | 3111 | 196 | 178 | 18 | 15 | 30.3 | 10 |
| synoptics_dp_2023 | 304 | 18.97 | 1 | 0 | 0.3 | 2584 | 286 | 226 | 45 | 4 | 38.9 | 4 |
| runwal_rhp_2026 | 611 | 44.96 | 0 | 0 | 0.0 | 6407 | 589 | 537 | 46 | 71 | 33.7 | 592 |
| moneyview_prospectus_2026 | 537 | 73.01 | 0 | 0 | 0.0 | 5132 | 320 | 306 | 14 | 0 | 38.2 | 530 |
| paytm_drhp_2021 | 497 | 48.38 | 1 | 0 | 0.2 | 5324 | 349 | 324 | 24 | 10 | 33.6 | 378 |
| sebi_draft_2010_probe | 214 | 9.27 | 0 | 0 | 0.0 | 2398 | 128 | 117 | 9 | 6 | 37.6 | 214 |
| indiqube_rhp_2025 | 607 | 56.91 | 4 | 0 | 0.7 | 5795 | 446 | 419 | 20 | 24 | 30.1 | 354 |
| vishal_mega_mart_udrhp_2024 | 366 | 33.07 | 0 | 0 | 0.0 | 3904 | 308 | 288 | 19 | 23 | 39.6 | 361 |
| laxmi_india_finance_rhp_2025 | 527 | 44.05 | 0 | 0 | 0.0 | 4643 | 537 | 503 | 32 | 20 | 52.5 | 515 |

### Extraction and checks (`rh analyze`, analysis v11)
| doc | values | citation-verified | footing passed | multi-source groups | unanimous | no period | no unit | issue facts verified | rules decisive | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| varyaa_prospectus_2024 | 176 | 176/176 (100%) | 6/6 (100%) | 24 | 22/24 (92%) | 23 | 31 | 4/4 (100%) | 3/4 | 0 |
| synoptics_dp_2023 | 255 | 255/255 (100%) | 7/7 (100%) | 42 | 34/42 (81%) | 36 | 14 | 6/6 (100%) | 4/4 | 0 |
| runwal_rhp_2026 | 433 | 433/433 (100%) | 15/19 (79%) | 45 | 38/45 (84%) | 27 | 52 | 3/3 (100%) | 2/5 | 0 |
| moneyview_prospectus_2026 | 342 | 342/342 (100%) | 30/30 (100%) | 67 | 64/67 (96%) | 112 | 24 | 5/5 (100%) | 3/5 | 0 |
| paytm_drhp_2021 | 237 | 237/237 (100%) | 3/3 (100%) | 22 | 10/22 (45%) | 87 | 41 | 3/3 (100%) | 2/4 | 1 |
| sebi_draft_2010_probe | 148 | 148/148 (100%) | 0/0 | 23 | 12/23 (52%) | 55 | 6 | 1/1 (100%) | 1/2 | 1 |
| indiqube_rhp_2025 | 335 | 335/335 (100%) | 21/21 (100%) | 45 | 39/45 (87%) | 138 | 66 | 4/4 (100%) | 3/6 | 0 |
| vishal_mega_mart_udrhp_2024 | 379 | 379/379 (100%) | 22/22 (100%) | 33 | 33/33 (100%) | 171 | 154 | 3/3 (100%) | 2/6 | 0 |
| laxmi_india_finance_rhp_2025 | 592 | 592/592 (100%) | 12/12 (100%) | 33 | 24/33 (73%) | 445 | 130 | 1/1 (100%) | 0/5 | 0 |

### Known defects (all measured, none hidden)
- Synoptics prints "31-Mar-22" over two columns of one table (a typo in the filing), so its FY2022
  total income is withheld as ambiguous.
- Several readings of "net worth", "total borrowings" and group-subsidiary lines make those
  concepts unreliable; the report lists the figures withheld.
- Many tables have no detectable unit; such values are never converted.
- Amounts with misplaced digit-group commas are rejected rather than guessed (about 1 in 7,900).
- OCR is not implemented. Indiqube has 4 pages with almost no text layer (flagged `needs_ocr`);
  they are skipped, not guessed.
- The sector detector and the "withheld" logic were calibrated on nine filings only.
- Citations use the PDF page index; printed page numbers are found on few SME pages.

---

(older entries below)

## 2026-10-24 (morning)

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

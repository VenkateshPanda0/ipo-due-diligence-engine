# Status

Latest first. Every number below was printed by `rh parse`, `rh analyze` or `rh eval` on the nine
filings in `data/sources.toml`; nothing is estimated.

## 2026-10-31

### Benchmark (`rh eval`, 566 labelled fields over thirty-three filings)
| set | docs | fields (present/absent) | value accuracy | citation accuracy | abstained | wrong | hallucinated |
|---|---|---|---|---|---|---|---|
| held-out sets 1 to 8, **first runs** | 24 | | 76%, 76%, 97%, 54%, 87%, 87%, 100%, 100% | | | | |
| held-out set 9, **first run** (two lenders, two SME drafts) | 3 | 54 (47/7) | 42/47 (89%) | 31/42 | 4 | 1 | 0/7 |
| set 9 after its fixes (no longer held out) | 3 | 54 (47/7) | 46/47 (98%) | | 1 | 0 | 0/7 |
| development, 30 filings | 30 | 506 (414/92) | 410/414 (99%) | 352/410 | 4 | 0 | 0/92 |
| held out: set 8 (not used for any fix) | 3 | 60 (46/14) | 46/46 (100%) | 42/46 | 0 | 0 | 0/14 |
| all thirty-three filings | 33 | 566 (460/106) | 456/460 (99%) | 394/456 | 4 | 0 | 0/106 |

Set 9 was the first lender and SME set since set 3 and read worse again (89%, one wrong value from a
lost header cell). Remaining abstentions: Spinaroo general corporate purposes (unitless table),
Tata Capital profit after tax FY2024 and Zetwerk profit after tax FY2026 and FY2025 (definitional
conflicts). `docs/heldout-run-9.md`.

## 2026-10-30

### Benchmark (`rh eval`, 512 labelled fields over thirty filings)
| set | docs | fields (present/absent) | value accuracy | citation accuracy | abstained | wrong | hallucinated |
|---|---|---|---|---|---|---|---|
| held-out sets 1 to 7, **first runs** | 21 | | 76%, 76%, 97%, 54%, 87%, 87%, 100% | | | | |
| held-out set 8, **first run** (extractor unchanged since set 7) | 3 | 60 (45/15) | 45/45 (100%) | 41/45 | 0 | 0 | 1/15 |
| set 8 with the label corrected (still held out: no extractor change) | 3 | 60 (46/14) | 46/46 (100%) | 42/46 | 0 | 0 | 0/14 |
| development, 27 filings | 27 | 452 (367/85) | 362/367 (99%) | 317/362 | 5 | 0 | 0/85 |
| all thirty filings | 30 | 512 (413/99) | 408/413 (99%) | 359/408 | 5 | 0 | 0/99 |

The single first-run "hallucination" was a labelling error (third in four runs): a draft says
"shall appoint" on one page and "has appointed [●]" on another. Set 8 caused no code change, so it
remains a held-out set. Drafts only; no lender or SME prospectus in SEBI's current listings
(`docs/heldout-run-8.md`).

## 2026-10-29

### Benchmark (`rh eval`, 452 labelled fields over twenty-seven filings)
| set | docs | fields (present/absent) | value accuracy | citation accuracy | abstained | wrong | hallucinated |
|---|---|---|---|---|---|---|---|
| held-out sets 1 to 6, **first runs** | 18 | | 76%, 76%, 97%, 54%, 87%, 87% | | | | |
| held-out set 7, **first run** (after set-6 fixes) | 3 | 60 (49/11) | 49/49 (100%) | 41/49 | 0 | 0 | 2/11 |
| set 7 after its fix (no longer held out) | 3 | 60 (49/11) | 49/49 (100%) | 41/49 | 0 | 0 | 0/11 |
| all twenty-seven filings now (every one has driven a fix) | 27 | 452 (367/85) | 362/367 (99%) | 317/362 | 5 | 0 | 0/85 |

Set 7 had no lender and no SME-platform prospectus (none in SEBI's current listing), so it says
little about those. Its two inventions were one defect: an amount from a pre-IPO placement entry
read as the offer for sale in a run-on glossary (`docs/heldout-run-7.md`).

## 2026-10-28 (evening)

### Benchmark (`rh eval`, 392 labelled fields over twenty-four filings)
| set | docs | fields (present/absent) | value accuracy | citation accuracy | abstained | wrong | hallucinated |
|---|---|---|---|---|---|---|---|
| held-out sets 1 to 5, **first runs** | 15 | see below | 76%, 76%, 97%, 54%, 87% | | | | |
| held-out set 6, **first run** (after set-5 fixes) | 3 | 58 (46/12) | 40/46 (87%) | 33/40 | 6 | 0 | 0/12 |
| set 6 after its fixes (no longer held out) | 3 | 58 (46/12) | 46/46 (100%) | 43/46 | 0 | 0 | 0/12 |
| all twenty-four filings now (every one has driven a fix) | 24 | 392 (318/74) | 313/318 (98%) | 276/313 | 5 | 0 | 0/74 |

Set 6 was the first run with the "re-read every absent label" check and found no labeller error.
All six first-run misses were one filing whose summary statements put row labels in the fourth
cell. Remaining abstentions are unchanged (Synoptics FY2022 total income; Tata Capital and
Zetwerk profit after tax, each a definitional conflict). See `docs/heldout-run-6.md`.

## 2026-10-28

### Benchmark (`rh eval`, 334 labelled fields over twenty-one filings)
| set | docs | fields (present/absent) | value accuracy | citation accuracy | abstained | wrong | hallucinated |
|---|---|---|---|---|---|---|---|
| held-out set 1, **first run** | 3 | 51 (41/10) | 31/41 (76%) | 29/31 | 6 | 4 | 0/10 |
| held-out set 2, **first run** (after set-1 fixes) | 3 | 49 (42/7) | 32/42 (76%) | 30/32 | 8 | 2 | 0/7 |
| held-out set 3, **first run** (after set-2 fixes) | 3 | 50 (39/11) | 38/39 (97%) | 35/38 | 1 | 0 | 0/11 |
| held-out set 4, **first run** (after set-3 fixes) | 3 | 51 (39/12) | 21/39 (54%) | 16/21 | 15 | 3 | 3/12 |
| held-out set 5, **first run** (after set-4 fixes) | 3 | 51 (38/13) | 33/38 (87%) | 27/33 | 4 | 1 | 2/13 |
| set 5 after its fixes and two label corrections (no longer held out) | 3 | 51 (40/11) | 38/40 (95%) | 30/38 | 2 | 0 | 0/11 |
| all twenty-one filings now (every one has driven a fix) | 21 | 334 (272/62) | 267/272 (98%) | 233/267 | 5 | 0 | 0/62 |

First runs: 76%, 76%, 97%, 54%, 87%. Two of the "hallucinations" in set 5 and one in set 4 were
the labeller's own errors (disclosed in `docs/heldout-run-4.md`, `-5.md`); labels still have no
second reader. Five abstentions remain: Synoptics FY2022 total income (duplicate header typo),
Tata Capital profit after tax FY2025 and FY2024 and Zetwerk profit after tax FY2026 and FY2025
(each a definitional conflict: owners' share vs total, or continuing vs total operations).

## 2026-10-27

### Benchmark (`rh eval`, 283 labelled fields over eighteen filings)
| set | docs | fields (present/absent) | value accuracy | citation accuracy | abstained | wrong | hallucinated |
|---|---|---|---|---|---|---|---|
| held-out set 1, **first run** | 3 | 51 (41/10) | 31/41 (76%) | 29/31 | 6 | 4 | 0/10 |
| held-out set 2, **first run** (after set-1 fixes) | 3 | 49 (42/7) | 32/42 (76%) | 30/32 | 8 | 2 | 0/7 |
| held-out set 3, **first run** (after set-2 fixes) | 3 | 50 (39/11) | 38/39 (97%) | 35/38 | 1 | 0 | 0/11 |
| held-out set 4, **first run** (after set-3 fixes) | 3 | 51 (39/12) | 21/39 (54%) | 16/21 | 15 | 3 | 3/12 |
| set 4 after its fixes (no longer held out) | 3 | 51 (40/11) | 38/40 (95%) | 33/38 | 2 | 0 | 0/11 |
| all eighteen filings now (every one has driven a fix) | 18 | 283 (232/51) | 229/232 (99%) | 203/229 | 3 | 0 | 0/51 |

Set 4 is the worst first run so far: three 1,000-page filings with subsidiary statements that also
foot, wrapped and kerned labels, and a cover table with a placeholder column. Three flagged
hallucinations of which one was a labeller error (disclosed and corrected in
`docs/heldout-run-4.md`). Honest reading of the first-run column: 76%, 76%, 97%, 54%; the extractor
does not yet generalise reliably to long, complex filings, and each batch has still exposed new
failure modes. Three abstentions remain (Synoptics FY2022 total income, Tata Capital PAT FY2025
and FY2024, where the filing's KPI tables print owners' profit and the statement total includes
minority interests: a definitional conflict the tool declines to guess).
Labels were written by the maintainer, an AI, with no second reader (`labels/README.md`).

## 2026-10-24 (evening)

### Benchmark (`rh eval`, 232 labelled fields over fifteen filings)
| set | docs | fields (present/absent) | value accuracy | citation accuracy | abstained | wrong | hallucinated |
|---|---|---|---|---|---|---|---|
| held-out set 1, **first run** | 3 | 51 (41/10) | 31/41 (76%) | 29/31 | 6 | 4 | 0/10 |
| held-out set 2, **first run** (after set-1 fixes) | 3 | 49 (42/7) | 32/42 (76%) | 30/32 | 8 | 2 | 0/7 |
| held-out set 3, **first run** (after set-2 fixes) | 3 | 50 (39/11) | 38/39 (97%) | 35/38 | 1 | 0 | 0/11 |
| all fifteen filings now (every one has driven a fix) | 15 | 232 (192/40) | 191/192 (99%) | 179/191 | 1 | 0 | 0/40 |

Read the first three rows, not the last. A filing stops being held out the moment a defect it
exposed is fixed. Sets 1 and 2 both scored 76%; set 3 scored 97% after the fixes from sets 1 and 2,
which says the earlier failure modes are gone, on a small and non-random sample. `docs/heldout-run-*.md` list every miss and its cause.
Labels were written by the maintainer, an AI, with no second reader (`labels/README.md`).

### Rules
Twelve rules. Regulatory ones now start on 10 Nov 2018 (ICDR 2018) unless a later amendment date
applies, so a 2005 draft is not judged by 2018 law. The cash-flow rule is not applied to lenders or
real-estate developers (sector detected from the front of the document). Flags currently raised
across twelve filings: Paytm trade receivables vs revenue (FY2020 to FY2021, checked against source
rows) and the Tanla 2005 draft's operating cash flow below profit in two of three years.

### Parser, twelve documents (parser v14)
| doc | pages | sec | OCR pages | err pages | % OCR | blocks | raw tbl | logical tbl | multi-pg | transposed? | % tbl w/ unit | printed pg # |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| varyaa_prospectus_2024 | 295 | 20.72 | 0 | 0 | 0.0 | 3111 | 196 | 178 | 18 | 15 | 34.3 | 10 |
| synoptics_dp_2023 | 304 | 19.9 | 1 | 0 | 0.3 | 2584 | 286 | 226 | 45 | 4 | 44.7 | 4 |
| runwal_rhp_2026 | 611 | 49.37 | 0 | 0 | 0.0 | 6407 | 589 | 537 | 46 | 71 | 41.2 | 592 |
| moneyview_prospectus_2026 | 537 | 72.28 | 0 | 0 | 0.0 | 5132 | 320 | 306 | 14 | 0 | 45.4 | 530 |
| paytm_drhp_2021 | 497 | 50.1 | 1 | 0 | 0.2 | 5324 | 349 | 324 | 24 | 10 | 47.5 | 378 |
| sebi_draft_2010_probe | 214 | 9.33 | 0 | 0 | 0.0 | 2398 | 128 | 117 | 9 | 6 | 37.6 | 214 |
| indiqube_rhp_2025 | 607 | 59.58 | 4 | 0 | 0.7 | 5795 | 446 | 419 | 20 | 24 | 37.7 | 354 |
| vishal_mega_mart_udrhp_2024 | 366 | 34.85 | 0 | 0 | 0.0 | 3904 | 308 | 288 | 19 | 23 | 50.0 | 361 |
| laxmi_india_finance_rhp_2025 | 527 | 47.32 | 0 | 0 | 0.0 | 4643 | 537 | 503 | 32 | 20 | 57.5 | 515 |
| leap_india_rhp_2026 | 474 | 56.42 | 0 | 0 | 0.0 | 4760 | 433 | 387 | 44 | 36 | 37.2 | 461 |
| shiprocket_udrhp_2025 | 543 | 76.67 | 0 | 0 | 0.0 | 5639 | 428 | 372 | 44 | 17 | 50.8 | 535 |
| indong_tea_prospectus_2022 | 259 | 20.62 | 0 | 0 | 0.0 | 2367 | 245 | 221 | 19 | 34 | 17.6 | 0 |

### Extraction and checks (`rh analyze`, analysis v15)
| doc | values | citation-verified | footing passed | multi-source groups | unanimous | no period | no unit | issue facts verified | rules decisive | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| varyaa_prospectus_2024 | 180 | 180/180 (100%) | 6/6 (100%) | 26 | 24/26 (92%) | 25 | 8 | 4/4 (100%) | 3/4 | 0 |
| synoptics_dp_2023 | 259 | 259/259 (100%) | 7/7 (100%) | 45 | 37/45 (82%) | 40 | 0 | 6/6 (100%) | 4/4 | 0 |
| runwal_rhp_2026 | 436 | 436/436 (100%) | 18/22 (82%) | 45 | 38/45 (84%) | 27 | 46 | 4/4 (100%) | 2/5 | 0 |
| moneyview_prospectus_2026 | 345 | 345/345 (100%) | 30/30 (100%) | 67 | 64/67 (96%) | 112 | 19 | 6/6 (100%) | 3/5 | 0 |
| paytm_drhp_2021 | 237 | 237/237 (100%) | 3/3 (100%) | 22 | 10/22 (45%) | 87 | 33 | 3/3 (100%) | 2/4 | 1 |
| sebi_draft_2010_probe | 148 | 148/148 (100%) | 0/0 | 23 | 12/23 (52%) | 55 | 6 | 1/1 (100%) | 1/2 | 1 |
| indiqube_rhp_2025 | 335 | 335/335 (100%) | 21/21 (100%) | 45 | 39/45 (87%) | 138 | 60 | 5/5 (100%) | 3/6 | 0 |
| vishal_mega_mart_udrhp_2024 | 379 | 379/379 (100%) | 22/22 (100%) | 33 | 33/33 (100%) | 171 | 102 | 4/4 (100%) | 2/6 | 0 |
| laxmi_india_finance_rhp_2025 | 592 | 592/592 (100%) | 12/12 (100%) | 33 | 24/33 (73%) | 445 | 130 | 1/1 (100%) | 0/5 | 0 |
| leap_india_rhp_2026 | 296 | 296/296 (100%) | 24/24 (100%) | 43 | 43/43 (100%) | 129 | 24 | 5/5 (100%) | 3/6 | 0 |
| shiprocket_udrhp_2025 | 552 | 552/552 (100%) | 15/15 (100%) | 38 | 38/38 (100%) | 273 | 82 | 4/4 (100%) | 2/6 | 0 |
| indong_tea_prospectus_2022 | 160 | 160/160 (100%) | 9/9 (100%) | 36 | 36/36 (100%) | 35 | 21 | 4/4 (100%) | 4/4 | 0 |

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
- Twelve rules exist; only those whose inputs were extracted can run (see `rules decisive`).

### Next
Label tooling and an evaluation harness; an LLM layer behind a cost cap (no API key exists in this
environment, so it will be built against a fake provider); segmenter; HTML report; red-team set for
prompt injection; CI step running the offline checks.

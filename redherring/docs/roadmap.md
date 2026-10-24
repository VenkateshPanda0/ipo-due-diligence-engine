# Roadmap

Status key: done / partial / not started. Updated whenever a milestone moves; the numbers behind
"partial" live in `status.md`.

## Foundation (M0) — done
Fetcher with integrity checks, page-tagged parser, tables, units, CLI, CI, decision log.

## Extraction (M1)
| Item | State |
|---|---|
| Parser quality on real filings (headers, fused cells, bands, continuations) | partial, improving; see `status.md` |
| Period parsing from column headers | done |
| Financial statement extractor with citations | partial: income, balance and cash-flow lines; ranking of duplicates by consensus |
| Label-free correctness checks (citation re-read, footing, cross-table consensus) | done for the three identities; more identities to add |
| Issue facts from the cover page and "Summary of the Offer" | not started |
| Objects of the issue (amounts, schedule, monitoring agency, GCP) | not started |
| Segmenter (map pages to ICDR sections) | not started |
| LLM layer: one interface, hard cost cap, on-disk cache, schema-checked output, injection defence | not started (no API key in this environment; will be built against a fake provider) |
| Labelling: JSON labels, validator, pre-fill from extractor | not started |
| RH-Bench harness: per-field accuracy, citation accuracy, hallucination rate | not started; needs labels |

## Red flags (M2)
| Item | State |
|---|---|
| Rule specs (TOML) and engine | done: ratio-vs-cap, required-if, persistent-below, growth-gap |
| Shipped rules citing primary text | nine rules (seven regulatory with clause and date, two heuristic with literature) |
| Rules needing facts not yet extracted (objects, issue size, OFS) | blocked on issue and objects extraction |
| Further rules: related-party, concentration, pledges, auditor, litigation, valuation vs peers | not started |
| Single-page HTML report with page citations | not started |
| Prompt-injection red-team set | not started |

## Version diff (M3)
DRHP to RHP to Prospectus, and abridged-prospectus consistency. Count post-March-2026 filings
first. Not started.

## Outcomes (M4)
Backtest only after hypotheses are written down; cut the SME backtest first if time is short.
Price data source must have terms that permit this use. Not started.

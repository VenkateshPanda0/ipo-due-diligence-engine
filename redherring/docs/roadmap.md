# Roadmap

Status key: done / partial / not started. The numbers behind "partial" live in `status.md`.
Updated 2026-10-24.

## Foundation (M0): done
Fetcher with integrity checks, page-tagged parser, tables, units, CLI, CI, decision log.

## Extraction (M1)
| Item | State |
|---|---|
| Parser quality on real filings | partial: nine filings, 0 error pages; unit missing on ~60% of tables |
| Period parsing | done (fiscal labels, "As at" mislabels, reversed years) |
| Financial statement extractor with citations | partial: seven concepts plus borrowings/net worth (unreliable) |
| Label-free checks (citation re-read, footing, cross-table consensus, column trust) | done |
| Issue facts and objects (amounts, GCP, unidentified acquisitions, monitoring agency) | done for stated amounts; placeholders never read |
| Sector detection (lender, real estate) | done, calibrated on nine filings |
| Segmenter (map pages to ICDR sections) | not started |
| LLM layer behind a hard cost cap, cache, schema-checked output, injection-safe prompts | built and tested against a fake provider; no API key here, so no LLM number exists |
| Labels, validator, eval harness with dev and held-out splits | done; 133 fields on nine filings |
| OCR for scanned pages | not started; no scanned test document yet |

## Red flags (M2)
| Item | State |
|---|---|
| Rule specs (TOML), engine, audit, validity windows, sector exclusions | done |
| Shipped rules | eleven (nine regulatory with clause and date, two heuristic with literature) |
| One-page HTML report per filing, figures linked to PDF pages | done (`rh report`) |
| Further rules: related-party, concentration, pledges, auditor, litigation, valuation | not started |
| Prompt-injection red-team set (hostile PDFs through parse and extract) | not started; prompt-level defences are tested |

## Next, in order
1. A third held-out set (three more filings, labels first). Sets 1 and 2 are now development data.
2. Rules from Schedule VI sections already parsed (related-party and promoter pledges first).
3. Segmenter, so rules can cite sections and the report can show them.
4. Red-team PDFs.
5. Version diff (count post-March-2026 filings before promising abridged-vs-full checks).
6. Outcome backtest only with written hypotheses and a price source whose terms allow it.

## Version diff (M3) and Outcomes (M4)
Not started; see above.

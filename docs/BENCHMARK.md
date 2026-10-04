# Real-document extraction benchmark — method

The benchmark measures how well the document-intelligence pipeline recovers the
Regulation 6(1) eligibility figures from real offer documents. Results are generated
into [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) and `benchmark/results/latest.json`.

## Corpus

Thirteen public Draft Red Herring Prospectuses filed with SEBI (Filings → Public Issues),
retrieved on 2026-10-04 and listed in `benchmark/manifest.json` with filing page, PDF
URL and SHA-256. They are public documents. The PDFs (~140 MB) are not committed;
`scripts/benchmark_extraction.py --download` fetches them and verifies the hashes.

| Split | Documents | Use |
|---|---|---|
| development | Madhur Iron & Steel, Ekkaa Electronics, JSW One Platforms, Iris Global Services, Jagatjit Agri Engineering, Iberia Pharmaceuticals, Vardaan Biotech, Anchor Offshore Services | Failure analysis and fixes. The last three were the first holdout; they were measured once (below) and then moved here. |
| holdout | Royal Chain, Hi-Tech Flow Solutions, M K C Agro Fresh, Maharashtra Oil Extractions, Ultravibrant Integrated Energy | **Measurement only.** Added after the code freeze (commit `96169ca`); answer keys committed (`c68c412`) before the first run. |

The documents cover lakh-denominated and million-denominated tables, Reg 6(1) and
Reg 6(2) issuers, consolidated and standalone columns, header layouts split across
cells and lines, units printed in row labels, and one table with no declared unit
(Jagatjit).

## Answer keys

`benchmark/ground_truth/<id>.json` lists, for each expected field: the field path, the
original printed text and unit, the expected ₹ crore value (or `null` where the
document declares no unit, so the correct behaviour is to abstain), the period, the
basis, and the expected page(s).

> **Limitation: the keys were prepared by an AI assistant from `pdftotext` (poppler)
> output, independently of the pipeline's code, and have not been verified by a
> human.** Each key says so in its `reviewer` field. Until a person checks them against
> the PDFs, the figures in BENCHMARK_RESULTS.md are indicative, not validated accuracy.

Keys are never edited to improve a score. A disagreement found during analysis is
reported in the results, not "fixed" in the key.

## Metrics

The denominator is the expected fields with a non-null value.

| Metric | Definition |
|---|---|
| correct | The selected value is within half a unit of the printed precision **and** the cited page is an expected page. |
| wrong | A value was selected but differs, or is right but cited from an unexpected page (`wrong_page`). |
| false_high | Wrong **and** marked `EXTRACTED_HIGH_CONFIDENCE`. This is the dangerous case. |
| flagged | Status is needs-verification or conflicting, whether right or wrong. |
| missing | No value was selected. |
| correct_abstention | For `null`-expected fields: no normalised value was produced. |
| precision / recall | correct / (correct + wrong) and correct / scored fields. |
| route_correct | The pipeline's Reg 6(1)/6(2) suggestion matches the route the DRHP states. |

The page check is strict. The same figure often appears in several sections (for
example a capitalisation statement and the eligibility table). The key names the
eligibility-table page, so a correct value cited from another page counts as
`wrong_page`.

## Running

```bash
.venv/bin/python scripts/benchmark_extraction.py --download             # fetch + verify PDFs
.venv/bin/python scripts/benchmark_extraction.py --run                  # all splits, OCR on
.venv/bin/python scripts/benchmark_extraction.py --run --split holdout --ocr off --no-write
```

A full run takes about 6–10 minutes on a laptop-class CPU (single process).

## Analysis of the 2026-10-04 run

**Baseline (before the 2.0.0 table fixes), development split, OCR off:** 13/48 correct,
11 wrong, 24 missing, 6 false-high. Precision 0.54, recall 0.27.

**After the fixes, all splits, OCR on:**

| | Development | Holdout |
|---|---|---|
| Correct (value and page) | 48/48 | 21/36 |
| Right value, unexpected page (`wrong_page`) | 0 | 6 |
| Wrong value | 0 | 0 |
| Missing (abstained) | 0 | 9 |
| False-high (all `wrong_page`) | 0 | 3 |
| Correct abstentions | 6/9 | — |

The fixes were driven only by development-split failures:

* Headers split across cells and lines.
* Per-column "(Consolidated)" / "(Standalone)" annotations.
* Unit captions on the previous page.
* Units printed in row labels.
* Footnote digits glued to labels.
* Rejecting "average" rows, cash-flow "operating profit before working capital
  changes", and "tangible net worth".
* Ignoring prose amounts like "₹ 30 million" as unit declarations.
* A higher section score for the Reg 6 eligibility table.
* Most importantly, rows whose numbers can't be placed unambiguously are now dropped,
  where previously they were shifted into the wrong year.

Holdout notes (measured, not tuned):

* **Vardaan Biotech:** 9 fields missing. For FY2026 and FY2024 the candidates had no
  determinable unit, so they were held back as needs-verification with no value. For
  FY2025 no candidate was found. The root cause has deliberately not been investigated
  on a holdout document. The 3 net-worth values are correct but were cited from p.320
  instead of the key's p.354 and marked high-confidence, so they count as `false_high`.
* **Anchor Offshore:** 3 PAT values are correct but cited from p.283, while the key
  lists four other pages. They were flagged as conflicting, not accepted.
* No holdout field received a wrong value.

Development still shows 3 "bad abstentions" on Jagatjit. Its p.509 eligibility table
declares no unit, but the same net-worth figures appear elsewhere in the DRHP with "₹
in million". So the extraction is defensible, and the key's "abstain" expectation
applies only to the p.509 table. The key was left unchanged; a human reviewer should
settle it.

## Round 2: fresh holdout (2026-10-04)

The first holdout's failures were diagnosed after it had been measured, and those
documents then moved to development. The causes:

* A header wrapped across two lines ("…ended March" / "31, 2025").
* Right-aligned figures under left-anchored headers.
* A prose sentence mistaken for a table header.
* A minority-interest "PAT … NCI" line and an "as per audited" profit row creating
  false conflicts.

The code was frozen once these were fixed. Five new DRHPs were then downloaded and
keyed, without running the pipeline on them.

| | Development (8) | Fresh holdout (5) |
|---|---|---|
| Correct (value and page) | 81/84 | **57/60** |
| Right value, unexpected page | 3 (Anchor PAT, see `benchmark/KEY_REVIEW_NOTES.md`) | 3 |
| Wrong value | 0 | **0** |
| Missing | 0 | **0** |
| False-high (all right-value / other-page) | 3 | 3 |
| Correct abstentions | 6/9 | — |
| Route detected | 8/8 | 5/5 |

The 3 holdout mismatches are Royal Chain's net-worth values. They are correct, but the
pipeline cited p.338 instead of the eligibility table on p.379, with high confidence.
Choosing the eligibility table is a scoring preference, not a correctness issue. It has
not been tuned, because Royal Chain is a holdout document.

Across both holdouts, no document has yet produced a **wrong value** for a scored field.
That is consistent with the design rule that ambiguous rows are dropped rather than
guessed. It is still based on 8 unseen documents and AI-prepared keys.

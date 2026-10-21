# M0 report: skeleton, ingest, parse

Branch `redherring/m0` (from `main` at `218b056`). Everything is under `redherring/` plus one new
workflow file, `.github/workflows/redherring.yml`. Not pushed.

**Read this first.** There is no ground truth yet (labelling starts in M1). Every number below is a
*heuristic measurement of parser output*, not an accuracy figure. Nothing here says the extracted
values are correct; it says what the parser found and where it visibly fell short.

## What exists

- `rh ingest`: robots-aware, rate-limited (3 s/host), size-capped fetcher; SHA-256 manifest; resumes
  cut-off transfers with HTTP Range; rejects non-PDFs and files lacking `%%EOF`.
- `rh parse`: page-tagged blocks and tables (`[PDF_PAGE_N]` from parser metadata only), scanned-page
  flag, multi-page table stitching, unit detection (₹ lakh / crore / million / thousand), Indian
  number parsing, tagged-text rendering, parse-quality table. Per-document failures do not stop the
  batch; output is cached by (PDF hash, parser version).
- 69 tests, ruff, mypy: all pass locally (see the end of this file). CI workflow written, **never
  run** (needs a push).

## Documents (4 of 5; document 5 awaits approval)

| doc_id | Document | Platform | Pages | Size |
|---|---|---|---|---|
| `varyaa_prospectus_2024` | Varyaa Creations Prospectus, Apr 2024 | SME (BSE) | 295 | 5.1 MB |
| `synoptics_dp_2023` | Synoptics Technologies *draft* prospectus, Mar 2023 | SME (NSE Emerge) | 304 | 5.4 MB |
| `runwal_rhp_2026` | Runwal Enterprises RHP, Sep 2026 | Mainboard | 611 | 18.1 MB |
| `moneyview_prospectus_2026` | Moneyview Prospectus, Sep 2026 | Mainboard | 537 | 15.8 MB |

Total 1,747 pages. **No scanned document yet**: only 1 page across all four has no text layer.

## Parse-quality table (final run, parser v2)

| doc | pages | sec | OCR pages | blocks | raw tbl | logical tbl | multi-pg | transposed? | printed pg # found |
|---|---|---|---|---|---|---|---|---|---|
| varyaa | 295 | 92.5 | 0 | 2722 | 230 | 187 | 34 | 14 | 10 |
| synoptics | 304 | 102.9 | 1 | 2283 | 313 | 218 | 52 | 4 | 4 |
| runwal | 611 | 259.4 | 0 | 5481 | 660 | 552 | 73 | 63 | 592 |
| moneyview | 537 | 230.8 | 0 | 4362 | 336 | 326 | 9 | 0 | 530 |

Speed: 0.31–0.43 s/page (pdfplumber, single process). A 600-page filing takes about 4–5 minutes.

Coverage metrics (my own heuristics; definitions in `scratchpad/metrics.py`, not committed):

| doc | numeric lines in tables | numeric lines left in prose | merged-value cells | numeric-heavy tables with a unit |
|---|---|---|---|---|
| varyaa | 549 | 7 | 71 | 56% |
| synoptics | 716 | 13 | 81 | 70% |
| runwal | 1,291 | 36 | 634 | 39% |
| moneyview | 1,303 | **636 (33%)** | 149 | 50% |

"Numeric line" = a line ending in at least two money-like tokens. "Merged-value cell" = a table cell
containing two or more money-like values.

## What worked

- Runwal's balance sheet comes out as one table stitched across 2 pages (90 rows), unit
  `million` detected from the caption.
- Moneyview's restated P&L (p96, p322) is recovered with total revenue, total income and profit
  across 5 periods, unit `million`.
- Page numbers are structural: tagged text carries physical PDF pages; printed page labels are kept
  separately.

## What failed or is unreliable

1. **Truncated downloads (found by the real SEBI files; fixed).** Both SEBI PDFs arrived cut off
   (2.1 of 18.1 MB, 1.9 of 15.8 MB). My fetcher accepted short bodies and trusted cached files. Now it
   compares against the server's length, resumes with Range, requires `%%EOF`, and re-fetches bad
   cached files. Five regression tests fail on the old fetcher and pass on the new one.
2. **Digits split by padding spaces (found on Moneyview; fixed).** Right-aligned numbers were padded
   with real space characters overlapping the first digit, so `9,521.29` came out as `9 ,521.29`.
   Spaces that sit inside a glyph's box are now dropped. Table cells with split digits in Moneyview:
   0 after the fix. The raw residue count I first reported (585) was mostly a false-positive regex.
3. **Transposed-table detection is unvalidated and probably over-triggers** (63 flagged in Runwal;
   none of the 3 I read looked like a correct flip). It used to flip rows; it now only sets
   `transposed_suspect` and leaves rows as found.
4. **Moneyview: 33% of numeric lines stay in prose** (131 pages, e.g. p35–36 KPI tables). The
   unruled-statement row builder needs at least 3 data rows and a numeric-looking page; other pages
   fall through. Open.
5. **Runwal: 634 merged-value cells.** Wide ruled tables (for example p292, statement of changes in
   equity) collapse several columns into one cell. Open.
6. **Multi-line column headers are not assembled** (e.g. Moneyview p322 header fragments are
   interleaved). Rows are right; headers need a pass in M1.
7. **Unit coverage is partial** (39–70% of numeric-heavy tables), and units can differ by table.
   Downstream code must treat a missing unit as "unknown", never "rupees".
8. **Printed page number detection is poor on the SME filings** (10 of 295, 4 of 304). Harmless
   today since citations use the PDF page, but not reliable.
9. **Scanned or image-heavy path is untested on real data.** OCR is not implemented; the
   `needs_ocr` flag is only exercised by a synthetic page.

## Not done

- Document 5 (older mainboard, ideally scanned): not downloaded, awaiting approval (see below).
- Count of post-March-2026 filings (needed before promising the abridged-vs-full check): not counted.
- Terms-of-use review of SEBI/BSE/NSE: only robots.txt was checked.
- Primary-source SEBI orders (Varyaa, Synoptics): not fetched; enforcement facts so far come from
  press reports.
- Local commits are unsigned (see `decisions.md`, D-013).

## Candidates for document 5 (headers only, nothing downloaded)

| Candidate | URL | Size | Note |
|---|---|---|---|
| One97 (Paytm) DRHP, 15 Jul 2021 | `sebi.gov.in/sebi_data/attachdocs/jul-2021/1626426805246.pdf` | 15.5 MB | Issuer unverified until page 1 is read. I could not find its final RHP on SEBI. |
| Old SEBI draft offer document (2010) | `sebi.gov.in/sebi_data/attachdocs/1292989425401.pdf` | 3.2 MB | Issuer unknown; chosen only as a plausible scanned candidate. |

## Proposed root `README.md` change (not applied)

Add a short "Related project: RedHerring" section linking to `redherring/README.md`. Nothing else.

## Changelog

1. Project skeleton, tooling, MIT licence copy, decision log, path-filtered CI.
2. Polite hashing fetcher with manifest; Range-resume and completeness checks after real downloads
   were truncated.
3. Page-tagged parser with tables, stitching, units, Indian-number parsing, scanned-page flag.
4. Fixes from real documents: digit-splitting spaces, unruled statements, row-label units,
   no silent row flipping, parser-versioned cache.
5. First parse-quality measurements on 4 filings (1,747 pages); six open defects listed above.

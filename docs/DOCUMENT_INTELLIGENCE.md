# Document intelligence pipeline

Code: `backend/app/intelligence/` (pipeline version `2.0.0`). Fully local and
deterministic: there are **no LLM or cloud calls**. Optional OCR uses the locally
installed Tesseract binary. Document content is never sent to a third party.

The pipeline turns a PDF into a *partial* `CompanyData` payload plus a per-field
decision record. A field is populated only when a candidate value was selected;
nothing is ever filled in by default. Every populated value is an `ExtractedValue` with
its page, original text, original unit, period, statement basis, method, confidence and
field status.

## Stages

| Stage | Module | What it does |
|---|---|---|
| A. Ingestion | `ingest.py` | Checks the file signature (not the filename or MIME type), enforces size and page limits, rejects encrypted PDFs, and repairs damaged PDFs with pikepdf or rejects them. It reports embedded JavaScript and attachments but never executes them. Stored names are server-generated. |
| B. Page classification | `pages.py` | Classifies each page as `native`, `scanned`, `rotated`, `garbled` or `blank`, using character count, upright ratio, garbled-glyph ratio and image coverage. Mixed documents are normal. |
| C. Native text | `pages.py` | Builds words from pdfium character boxes (loose boxes, upright detection, generated characters skipped). This is about 30× faster than pdfminer on 400–600-page DRHPs. |
| D. Tables | `tables.py` | Two independent strategies (see below). pdfplumber's ruled-table extraction runs only on pages that look tabular. |
| E. OCR fallback | `ocr.py` | Applies only to pages that need it, within per-document page and time budgets. Steps: pdfium render, then Tesseract OSD rotation, then projection-profile deskew, then word boxes with confidences. A page that needed OCR but couldn't get it is reported as **unreadable**, never as an empty valid page. |
| F. Semantic labels | `lexicon.py` | Positive patterns with strengths, plus negative patterns that veto a match (see the exclusions below). |
| G. Candidates | `candidates.py` | One candidate per field × period × table cell, with a documented score (see below). |
| H. Normalisation | `numbers.py`, `periods.py` | Handles Indian and international digit grouping, all common negative forms, and null markers (`–`, `NA`, `nil`, `[●]`), which are never treated as zero. Units are converted to ₹ crore **only when a unit is declared**. Periods are labelled `FY<yyyy>` for March year-ends, `YE<yyyy-mm>` for other year-ends, and `P<date>-<n>M` for stubs. |
| I. Validation | `candidates.py` | Clusters candidates by value within the printed precision, detects conflicts, and runs cross-field sanity checks (for example, NTA or net worth greater than total assets downgrades confidence). |
| J. Assembly | `pipeline.py` | Builds the partial `CompanyData`. The period end and month count come from the selected column. |
| K. Confidence | `candidates.py` | Assigns a field status: `EXTRACTED_HIGH_CONFIDENCE`, `EXTRACTED_NEEDS_VERIFICATION`, `CONFLICTING_CANDIDATES` or `NOT_FOUND`. |
| L. Human review | `services/documents.py`, `services/cases.py` | Opens a review item for every value that is not high-confidence. Extraction **never overwrites** a value a human entered or confirmed. |

Narrative facts (`narrative.py`: listing-route statements, document type, auditor
remarks) are always `EXTRACTED_NEEDS_VERIFICATION`. Suggestions such as "the DRHP
states Reg 6(2)" are shown to the user. They never overwrite case fields.

## Table reconstruction

**Geometric** (works for native and OCR words). A header line is one that holds two or
more distinct, left-to-right reporting periods. Period matching checks cell by cell and
also across the whole line; the second check handles headers split into "March" | "31,"
| "2025". Multi-line headers are handled too: "Fiscals" / "Description" above a row of
bare years. Each number below the header is assigned to the nearest period column by x
position. The following safety rules apply:

* **Ambiguous rows are dropped, not guessed.** A row is skipped with a table warning if
  a number falls outside every column, two numbers compete for one column, or there are
  more numbers than columns. Guessing here would silently shift values between years.
* Running prose that crosses the value columns (footnotes, narrative) is not a row.
* Wrapped row labels are merged. A table that continues onto the next page inherits
  the header.
* The **unit** is taken from the header, a caption within 10 lines above it (including
  the last lines of the previous page), or the page heading. A unit printed in the **row
  label** ("Net worth (in ₹ million)") overrides those, except that a bare "(₹)" does
  not override a scaled caption. Amount phrases in prose ("at least ₹ 30 million") are
  not unit declarations.
* The **statement basis** is taken per column from "(Consolidated)" / "(Standalone)"
  annotations next to the header, otherwise from captions.
* A table counts as an **eligibility table** when the ~40 lines above it, across a page
  break, discuss ICDR eligibility or Regulation 6.

**Vector**: pdfplumber ruled tables with a period header row, interpreted by column
index, borrowing caption context from the geometric view.

## Label exclusions

These are deliberate. They exist because the baseline mapped them wrongly (defect D9),
or because they were found on real DRHPs during benchmarking:

* Profit before tax, EBIT, EBITDA, "after tax", **averages**, **margins** and
  "operating profit before working capital changes" (a cash-flow line) are **not**
  operating profit. Pre-tax *operating* profit is.
* "Cash and cash equivalents" alone is not monetary assets.
* Return on net worth, net worth per share, **tangible net worth** (an industry and
  peer metric) and non-controlling interest are not net worth.
* Ratios, growth rates and per-share figures never match amount fields.
* Labels are normalised before matching. Glued footnote digits ("assets1"), hyphens
  ("net-worth"), unit markers and "(1)"/"(a)" markers are stripped.

## Candidate score (0–1)

| Weight | Component | Values |
|---|---|---|
| 0.35 | label strength | 1.0 exact / defined term … 0.6 weak synonym |
| 0.20 | source quality | native table 1.0; OCR scaled by word confidence |
| 0.15 | unit evidence | header / caption / row label 1.0; page heading 0.8; none 0 |
| 0.10 | period quality | 12-month 1.0; stub 0.7 |
| 0.10 | basis | consolidated 1.0; unknown 0.6; standalone 0.5 |
| 0.10 | section | Reg 6 eligibility table 1.0; restated / summary 0.75; other 0.5 |

Decision rules:

* Consolidated candidates are preferred. Otherwise unknown-basis and standalone
  candidates compete on score.
* Clusters that disagree with scores within 0.15 of each other give
  `CONFLICTING_CANDIDATES`. Conflicts are never resolved silently.
* `EXTRACTED_HIGH_CONFIDENCE` requires all of: a score ≥ 0.72 (≥ 0.78 for the
  critical Reg 6 fields); a declared unit; native text (not OCR); and either two
  independent sources or a recognised eligibility or summary section.
* A value whose unit is unknown is kept as a raw candidate. It is never normalised and
  never selected.

## What this does not do

* There is no LLM, no cloud OCR and no handwriting recognition.
* It does not read graphs or charts.
* Non-English DRHPs are not supported. Tesseract runs with `eng` only.
* Values that appear only in prose (not in a table) are not extracted, except the
  narrative facts listed above.
* The lexicon covers the Reg 6 fields plus revenue, PAT, total assets and liabilities,
  paid-up capital, reserves and EBITDA. Governance, RPT and litigation inputs are
  entered manually.

## Accuracy

See [BENCHMARK.md](BENCHMARK.md) for the method and
[BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) for the latest measured results on 8 public
SEBI DRHPs. The answer keys are **not human-verified**, so treat the numbers as
indicative.

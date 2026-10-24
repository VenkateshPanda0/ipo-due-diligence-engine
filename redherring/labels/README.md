# RH-Bench labels

One JSON file per filing (`<doc_id>.json`), validated by `rh label-check` against the PDF text
layer. `rh eval` scores the extractor's output against them.

## Format

Each field is `issue.*`, `objects.*` or `financials.<concept>.<FYyyyy>` with a status:

- `present`: `value_rupees` (full rupees), `raw` (as printed), `pages` (every page where the labeller
  found the statement), `span` (the printed line carrying `raw`).
- `absent`: the document does not state it (placeholder `[●]`, not applicable, or never mentioned).
  A prediction for an absent field is a hallucination.
- `unsure` / `unreviewed`: excluded from scoring.

`split` is `dev` (the extractor was built against these filings) or `heldout` (labelled before the
extractor was run on the filing and not tuned on it; see `docs/decisions.md` D-021). Quote
held-out numbers, not development numbers, when asking how well the tool generalises.

## How the labels were made, and what that does not show

The labeller is the maintainer, an AI. Each value was read from the PDF with poppler's
`pdftotext -layout`, a different extraction path from the extractor's pdfplumber/pypdfium2, and
typed into a spec; a script then located pages and spans mechanically. There is **no
inter-annotator agreement** and no human second reader, so label errors are possible. Where a
filing contradicts itself (for example summary tables that call total comprehensive income
"profit for the year"), the label follows the primary restated statement and says so in `note`.

## Scoring rules

A predicted value is correct when it is within the coarser printed precision of the label (so
538.02 and 538.03 agree; 2,239.30 and 2,239.15 do not). Citation accuracy requires the cited page
to be one of the label's `pages`. Abstaining on a present field is counted separately from being
wrong.

# Held-out run 7 (2026-10-29): three more unseen filings, after the run-6 fixes

Procedure as before (D-021, D-034): Sahajanand Medical Technologies RHP (569 pages, a pure offer
for sale), Fusion CX RHP (559 pages) and Swastika Infra RHP (460 pages, ₹ lakhs with Indian digit
grouping) were taken from SEBI's public RHP listing; their 60 labels were committed (`29b7b45`)
and only then was the extractor run. Every "absent" label was re-read on the cover and objects
pages before commit. The roadmap asked for a lender and an SME-platform prospectus; neither was in
SEBI's current RHP listing, so this set is three mainboard RHPs from 2026 and does not test those.

| | held-out set 7, first run |
|---|---|
| labelled fields | 60 (49 present, 11 absent) |
| value accuracy | 49/49 (100%) |
| citation accuracy of correct values | 41/49 (84%) |
| abstained | 0/49 |
| wrong value | 0/49 |
| hallucinated (value for an absent field) | 2/11 |

First runs so far: 76%, 76%, 97%, 54%, 87%, 87%, 100%. Every present field was read correctly, but
two values were produced for fields that are absent, and both were real extractor defects (not
label errors): the labels were re-read after the run and stand. All three filings are recent,
well-formed mainboard RHPs; 100% here says the tool copes with that kind of document, not that it
will on a lender, an SME prospectus or a scanned filing.

## Causes

Both inventions were in Swastika Infra. The glossary on page 14 defines "Offer for Sale" and, a few
lines further, "Pre-IPO Placement" with "aggregating to ₹4,000.00 lakhs". Glossary entries run on
without a sentence break, so the offer-for-sale amount pattern reached across the next entry and
took the placement's 4,000.00 lakhs as the offer for sale (the real figure is [●]). The total was
then derived as fresh issue 12,900.00 + 4,000.00 = 16,900.00 lakhs, so a wrong value became a
second wrong value. Both cite page text that really does contain those numbers, which is why
citation verification could not catch them.

## Fix (so set 7 is now development data)

The gap between "Offer for Sale" or "Fresh Issue" and its amount may not contain "pre-IPO" or
"private placement". A test reproduces the glossary run-on and fails without the fix. After the
fix: 49/49, 0 wrong, 0/11 invented, citation 41/49 (the eight misses are cited pages that print
the figure, mostly the cover page, but are not in the label's page list). The 24 earlier filings
did not change (313/318).

An eighth held-out set should include a lender and an SME prospectus; until SEBI's listing has
one, SME prospectuses from earlier listings are the fallback.

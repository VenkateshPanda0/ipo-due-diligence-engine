# Held-out run 8 (2026-10-30): three draft documents, extractor unchanged

Procedure as before (D-021, D-034). Carlsberg India UDRHP-I (521 pages), Inox Air Products DRHP
(689 pages) and Electromech Infraprojects DRHP (518 pages) were taken from SEBI's public draft
listing; their 60 labels were committed (`8d04610`) and only then was the extractor run, with the
code exactly as it stood after run 7. These are draft documents (price and several amounts are
[●], monitoring agency often "to be appointed"), unlike sets 6 and 7. SEBI's current listings
still had no lender, and the SME platform is not listed there at all, so lenders and SME
prospectuses remain untested by any held-out set since set 3.

| | held-out set 8, first run |
|---|---|
| labelled fields | 60 (45 present, 15 absent) |
| value accuracy | 45/45 (100%) |
| citation accuracy of correct values | 41/45 (91%) |
| abstained | 0/45 |
| wrong value | 0/45 |
| hallucinated (value for an absent field) | 1/15 |

First runs so far: 76%, 76%, 97%, 54%, 87%, 87%, 100%, 100%.

## A label error, disclosed

The one "hallucination" was mine. Electromech's draft says on p101 that the company "shall ... appoint a
monitoring agency ... prior to filing of the Red Herring Prospectus", and I labelled the field
absent. The general-information section (p152) says "our Company has appointed [●], as the
monitoring agency" (the name is blank in the draft). My first search printed only the first four
hits and missed p152. The filing states both, as Lenskart's did (run 4), and the same rule
applies: the general-information statement counts. Label corrected to present (value 1); the
extractor was right. After correction: 46 present, 14 absent, 46/46 correct, 0/14 invented,
citation 42/46 (the misses are cited pages that print the figure but are not in the label's page
list). That is the third label error in four runs, always in a field I called absent after
reading one page; labels still have no second reader.

## What this run does and does not show

No extractor change was made, so set 8 is **still held-out**: its numbers describe the code as
shipped, and the next set can be compared to it. All three documents are clean modern filings
with 3 to 5 fiscal-year columns; Electromech mixes consolidated FY2026 with standalone earlier
years in one balance sheet, and the tool read the printed columns as labelled. 100% on such
documents is not evidence about lenders, SME prospectuses or scanned filings.

All 30 filings together: 408 of 413 present fields correct (99%), 0 wrong, 0 invented in 99
absent fields (the five abstentions are the old ones).

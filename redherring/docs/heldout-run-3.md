# Held-out run 3 (2026-10-26): Powerica, SRIT India, Veritas Finance

Procedure as before (D-021): downloaded, 50 labels committed (`529de5a`), then the extractor was run
once. The three filings: a manufacturer's RHP whose amounts are in crore and whose income statement
is headed "As at" (Powerica); a DRHP with wrapped row labels and no price yet (SRIT India); an
offer-for-sale-heavy NBFC DRHP (Veritas Finance).

| | held-out set 3, first run |
|---|---|
| labelled fields | 50 (39 present, 11 absent) |
| value accuracy | 38/39 (97%) |
| citation accuracy of correct values | 35/38 (92%) |
| abstained | 1/39 |
| wrong value | 0/39 |
| hallucinated (value for an absent field) | 0/11 |

Runs 1 and 2 scored 76% each. This one scored 97%, so the fixes made after those runs did carry to
filings that were not used to build them: the "As at" income statement, the three-column cover
table, crore units and captionless statements all appeared again and were handled. Three filings
and 39 present fields are a small sample; the three are also not a random draw (one NBFC, one
price-less draft, one manufacturer). Read it as "the earlier failure modes are gone", not as "97%
is the accuracy".

The 3 citation misses are label-side: the extractor cited the cover page (1 or 4) for the issue
sizes and the labeller had listed other pages for the same statement; the cited text does contain
the figure.

## The one miss

Veritas Finance total assets FY2024 was withheld. The ruled summary balance sheet puts its
right-aligned figures up to two cells left of the left-aligned "As at March 31, 2024" headers, and
rows are aligned differently from one another, so the figure had no period. A figure column with
no dated header of its own now takes the nearest dated header within two cells (right on a tie);
where figures already sit under their headers nothing changes. That makes this set development
data too; the next generalisation figure needs set 4.

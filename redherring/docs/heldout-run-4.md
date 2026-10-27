# Held-out run 4 (2026-10-27): three large unseen filings, after the run-3 fixes

Procedure as before (D-021): Lenskart RHP (1,528 pages), Tata Capital RHP (1,023) and PhysicsWallah
RHP (405) were downloaded, their 51 labels were committed (`f3c4fc0`), and only then was the
extractor run. Nothing was tuned in between.

| | held-out set 4, first run |
|---|---|
| labelled fields | 51 (39 present, 12 absent) |
| value accuracy | 21/39 (54%) |
| citation accuracy of correct values | 16/21 (76%) |
| abstained | 15/39 (38%) |
| wrong value | 3/39 (8%) |
| hallucinated (value for an absent field) | 3/12 |

This is the worst first run so far (76%, 76%, 97%, 54%). Run 3's 97% was a small, favourable
sample; these are much larger documents, where a figure appears in many more tables and the
filing also carries statements of subsidiaries and peers that foot just as well as the issuer's.

## A label error, disclosed

One of the three "hallucinations" was my error: Lenskart's monitoring agency was labelled absent
from page 226 ("will appoint") while page 133 says "Our Company has appointed CARE Ratings
Limited". The label was corrected to present (the filing says both; the General Information
statement and the agreement of 14 Oct 2025 favour "appointed"). The first-run figures above are
against the labels as committed, so they include that mistake; after correction the set is 40
present / 11 absent. Labels have no second reader, which is exactly the risk this shows.

## Causes

| area | symptom | cause |
|---|---|---|
| cover table | wrong fresh/OFS/total amounts, invented OFS | a placeholder column ("[●]") shifted the amounts when the table was flattened to text; amounts were read by order of appearance |
| tax label | abstained | "Tax expenses/(credit)" and "Net tax expenses" not recognised |
| PAT label | abstained | wrapped labels with an unclosed parenthesis; "Profit for the period/year from continuing operations" truncated by a line break |
| kerned text | total income abstained | "T otal" split by letter spacing in the label |
| subsidiary statements | wrong total assets, total income, PAT | subsidiary or "excluding subsidiary" columns foot and tie with other pages, and out-voted the consolidated figure by sheer repetition |

## Fixes (so set 4 is now development data)

- Cover amounts are read positionally from the cover table (columns Fresh Issue, Offer for Sale,
  Total), and a row so read is not read again from text.
- Label variants for tax, PAT and total income; the "T otal" kerning is repaired; a figure column
  with a blank header takes the nearest dated header within two cells.
- Consensus: a reading in the front quarter of the document weighs double; a reading under a
  column headed "excluding", "standalone", "subsidiary", "segment" or "pro forma" weighs nothing;
  an untrusted column that agrees with a trusted figure corroborates it; for size concepts a narrow
  lead is kept only if it is also the largest figure (a subsidiary cannot exceed its group). A
  cash-flow statement's "profit before tax" is no longer a rival reading of the income statement.
- After the fixes: 38/40 (95%), 0 wrong, 0/11 hallucinated, 2 abstained (Tata Capital PAT FY2025
  and FY2024: the KPI tables print profit attributable to owners, 36,646.6 million, while the
  label is the statement total including minority interests, 36,550.2 million; the tool declines
  to guess). The 15 development filings did not change (191/192).

These numbers are no longer held-out. A fifth set is needed before quoting a new generalisation
figure.

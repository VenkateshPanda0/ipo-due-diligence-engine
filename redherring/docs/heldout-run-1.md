# Held-out run 1 (2026-10-24): first contact with three unseen filings

Procedure (D-021): the three filings were downloaded, their labels (51 fields) were written and
committed (`506ff4f`), and only then was the extractor run on them. Nothing was tuned in between.
This is the number to quote for "how well does it work on a filing it has not seen".

| | held-out, first run |
|---|---|
| labelled fields | 51 (41 present, 10 absent) |
| value accuracy | 31/41 (76%) |
| citation accuracy of correct values | 29/31 (94%) |
| abstained | 6/41 (15%) |
| wrong value | 4/41 (10%) |
| hallucinated (value for an absent field) | 0/10 |

On the six development filings the same code scored 69/70 correct (99%) after tuning; the gap
between 99% and 76% is the overfitting that this procedure exists to expose.

## What went wrong, and the cause of each miss

| doc | field | outcome | cause |
|---|---|---|---|
| Indiqube | `issue.ofs_amount` | wrong (6,500 vs 500 million) | cover table flattens to "Offer for Sale | Fresh issue ... ₹6,500 | Offer for sale ... ₹500"; the pattern for OFS took the first amount after the heading, which is the fresh-issue cell |
| Laxmi India Finance | total income, revenue, PBT (FY2025/24) | abstained or wrong (44.71) | statement lines start with a roman numeral without a full stop ("III Total Income (I+II)") so no label matched; a note's sub-total "Total Income" of one line item then won FY2024 |
| Laxmi India Finance | PAT FY2025/FY2024 | wrong (359.10, 226.20 vs 360.05, 224.68) | a ratio table's "Net Profit after tax (Including OCI)" (comprehensive income) was read as profit |
| Laxmi India Finance | CFO | correct but cited page 44 not in label | label page list incomplete, not an extractor error |
| Vishal Mega Mart | total assets FY2024/FY2023 (abstained) | a rectangle drawn around three rows' value cells made a label-less fragment and split the balance sheet in three tables, so assets and equity-and-liabilities never met in one table to foot |

Every wrong value was caught by the design only partially: none was caught by citation
verification (each number really is on the cited page), which is why a held-out label set matters
more than the label-free checks for this class of error.

## Fixes made afterwards (so these three filings are now development data)

Issue extractor: a role's amount may not be taken across the other role's wording. Labels: bare
roman numerals, "Operating Activity". Rejection: "including/after OCI". Parser v10: a label-less
ruled box over part of a statement is re-read with the statement. Each fix has a test that fails
without it. A further held-out set is needed before claiming the post-fix number; see
`docs/roadmap.md`.

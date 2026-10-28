# Held-out run 6 (2026-10-28): three more unseen filings, after the run-5 fixes

Procedure as before (D-021, D-034): Shah Investor's Home RHP (broking and financial services,
₹ lakhs, 715 pages), Orient Cables (India) RHP (491 pages) and Nityas Gems and Jewellery RHP
(537 pages) were taken from SEBI's public RHP listing; their 58 labels were committed (`7d8aec5`)
and only then was the extractor run. New this time: every "absent" label was re-read on the cover
and objects pages before commit, which is the check run 5 called for. All three print the price
as [●] (Nityas also as [•]), so most issue-size fields are genuinely absent; Shah is a fresh issue
with no offer for sale.

| | held-out set 6, first run |
|---|---|
| labelled fields | 58 (46 present, 12 absent) |
| value accuracy | 40/46 (87%) |
| citation accuracy of correct values | 33/40 (82%) |
| abstained | 6/46 (13%) |
| wrong value | 0/46 |
| hallucinated (value for an absent field) | 0/12 |

First runs so far: 76%, 76%, 97%, 54%, 87%, 87%. No label error was found this time, but that is
one run; labels still have no second reader.

## Causes

All six abstentions were in one filing, Shah Investor's Home (total income and profit after tax
for both years, total assets for both years). Its summary statements put the row label in the
fourth cell (`Sr. No. | blank | blank | label | figures`), and the label-column search looked only
at the first three cells, so the two summary tables were not read at all; the remaining readings
came from other pages and disagreed with each other or were missing. After that fix one reading
remained: total assets FY2026 printed 30,443.85 under a dateless caption "Consolidated", with the
dated header "Year ended March 31, 2026" in the next cell, so it carried no period.

## Fixes (so set 6 is now development data)

The label column is searched among the first five cells. A dateless caption over figures borrows
the adjacent dated header when that header's own column holds no figures. Each fix has a test
that fails without it. After the fixes: 46/46 (100%), 0 wrong, 0/12 invented, citation 43/46
(93%; the misses are cited pages that print the figure but are not in the label's page list).
The 21 earlier filings did not change (267/272).

A seventh held-out set is needed before quoting a new generalisation figure.

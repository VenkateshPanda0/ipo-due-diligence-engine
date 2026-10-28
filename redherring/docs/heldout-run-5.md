# Held-out run 5 (2026-10-28): three more unseen filings, after the run-4 fixes

Procedure as before (D-021): Zetwerk Manufacturing Businesses RHP (762 pages, Oct 2026), Tonbo
Imaging India RHP (554 pages, Oct 2026) and Paras Healthcare RHP (651 pages, Oct 2026) were
picked from SEBI's public RHP listing, their 51 labels were committed (`723f591`), and only then
was the extractor run. All three print the price as [●], so several issue-size fields are
genuinely absent; Tonbo is a pure offer for sale.

| | held-out set 5, first run |
|---|---|
| labelled fields | 51 (38 present, 13 absent) |
| value accuracy | 33/38 (87%) |
| citation accuracy of correct values | 27/33 (82%) |
| abstained | 4/38 (11%) |
| wrong value | 1/38 (3%) |
| hallucinated (value for an absent field) | 2/13 |

First runs so far: 76%, 76%, 97%, 54%, 87%. The 3,000-page-class difficulty of run 4 was not
repeated, and these filings are smaller, but no trend should be read into five samples of three.

## Two label errors, disclosed (both were the labeller's)

Both "hallucinations" were my mistakes, found by reading the cited pages after the run; the
first-run figures above are against the labels as committed.

| field | label as committed | what the filing says |
|---|---|---|
| Paras Healthcare `issue.ofs_amount` | absent (read from p3 wording, where the share count is [●]) | the cover table (p1) and p3 print "9,500.00 million" for the offer for sale; the extractor was right |
| Tonbo `objects.monitoring_agency_appointed` | absent | p108: "our Company is not required to appoint a monitoring agency", a stated value of 0, labelled that way for Indong Tea in set 2 |

Corrected labels: 40 present, 11 absent. This is the second run in a row with a labeller error
of the same kind (reading one page and calling a field absent); labels have no second reader.

## Causes of the genuine misses

| area | symptom | cause |
|---|---|---|
| headers | Tonbo profit after tax FY2026 abstained | headers "2026", "Fiscal 2025", "2024": a spanning caption printed once leaves bare-year headers undated |
| label | Tonbo profit after tax | "Restated Profit for the year, net of Tax" not matched |
| cash flow | Tonbo cash from operations FY2025 wrong (1,029.03 vs 1,361.19) | "Cash generated from Operating Activities" is the subtotal before tax and was read as the headline; the net line "(A) = i+ii+iii" was not matched, so it could not take precedence |
| stub column | Tonbo cash from operations FY2026 abstained | a blank-headed June-2026 stub column borrowed the FY2026 header from its neighbour, giving two FY2026 readings per table, which are dropped as ambiguous |
| definition | Zetwerk profit after tax FY2026, FY2025 abstained | the statement prints continuing-operations and total (with discontinued) results; "Restated loss for the period/year" is the label's total, and both readings are present in many tables |

## Fixes (so set 5 is now development data)

A bare-year header takes the wording of the dated header beside it (on its left once that is
dated, else the next on its right), so "2024" after a June-2025 quarter is a June-2024 quarter,
after "Fiscal 2025" a fiscal year. "net of tax" and an unbracketed "= i+ii+iii" formula are
accepted in labels. Where a table has a "net cash ... operating activities" line, the "cash
generated from operating activities" subtotal is not read as operating cash flow. A blank-headed
figure column left of the first dated header, beside a dated header column that holds figures of
its own, stays undated. Each has a test that fails without it.

A first attempt at the stub rule (never lend a dated header to a column whose own header column
holds figures) cost two correct Veritas total-assets readings and was reverted before commit; the
final rule is narrower. After the fixes: 38/40 (95%), 0 wrong, 0/11 hallucinated, 2 abstained
(Zetwerk profit after tax, a definitional conflict the tool declines to guess), citation 30/38.
The 8 citation misses are cited pages that do print the figure (cover page 1, restated
statements p334, a risk-factor page) but are not in the label's page list: label incompleteness,
as noted for earlier sets. The 18 earlier filings did not change (229/232).

A sixth held-out set is needed before quoting a new generalisation figure.

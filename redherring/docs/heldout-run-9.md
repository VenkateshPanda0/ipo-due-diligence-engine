# Held-out run 9 (2026-10-31): two lenders and two SME drafts

Procedure as before (D-021, D-034, D-037), using the new `tools/` (D-038): Neev Credit DRHP (an
NBFC on the SME platform, hosted by BSE), Aadhar Housing Finance RHP (a mainboard housing lender,
hosted by its lead manager) and Spinaroo Commercial DRHP (another SME draft, hosted by BSE) were
chosen because sets 6 to 8 had no lender and no SME filing. Their 54 labels were committed
(`a1e24be`) and only then was the extractor run, with the code as it stood after run 7 (set 8's
changes were labels only). Every "absent" label was audited against all matching lines with
`label_build.py --audit-absent` before commit; none was changed by the audit.

| | held-out set 9, first run |
|---|---|
| labelled fields | 54 (47 present, 7 absent) |
| value accuracy | 42/47 (89%) |
| citation accuracy of correct values | 31/42 (74%) |
| abstained | 4/47 |
| wrong value | 1/47 |
| hallucinated (value for an absent field) | 0/7 |

First runs so far: 76%, 76%, 97%, 54%, 87%, 87%, 100%, 100%, 89%. The lenders and SME drafts are the
first filings of those kinds since set 3 and they cost accuracy again, as the early sets did. No
label error was found this time.

## Causes

| area | symptom | cause |
|---|---|---|
| headers | Neev operating cash flow FY2023 **wrong** (321.29 lakhs, which is FY2024's figure) | the cash-flow table lost its first header cell ("Year Ended 31.03.2024"), so every figure sat one year late; the table repeats on a second page, so two readings outvoted the one correct reading |
| unit | Spinaroo total assets FY2024 and FY2023 abstained | the balance sheet has no unit caption; the caption "(Rs. In lakhs)" is over the P&L on the next page, and units were only borrowed from statements before |
| wording | Neev total issue abstained | the cover calls the whole raise the "Public Issue" ("aggregating up to ₹1500.00 lakhs (“PUBLIC ISSUE”)") and only "Offer" and "Issue" were recognised as the total |
| unit | Spinaroo general corporate purposes abstained | the objects table prints "200.00" with no unit anywhere on its page |

## Fixes (so set 9 is now development data)

- A (table, period) column whose revenue, income and profit figures all contradict a decisive
  consensus for the period it is dated is set aside, with everything else read from it (analysis
  field `columns_quarantined`). "Decisive" means two or more supporters and at least double any rival.
- A statement without a unit caption takes the unit of the statement within two pages after it
  when no earlier statement supplies one (same dates, all donors agree; parser v15).
- "Public Issue" is a defined term for the total.
- Not fixed: the unitless objects table (Spinaroo GCP). The tool abstains; guessing a unit for a
  table with no caption would be worse.

After the fixes: 46/47 correct (98%), 0 wrong, 0/7 invented, 1 abstained (the GCP above). The fixes also
resolved two older abstentions (Tata Capital profit after tax FY2025 and Synoptics total income
FY2022). Development accuracy is now 410/414 (99%) over 30 filings; set 8, which these fixes were
not derived from, stays held out and still reads 46/46.

SEBI's own listings still had no lender, so these came from exchange and lead-manager sites;
those hosts' files are public documents but their dates were checked on page 1.

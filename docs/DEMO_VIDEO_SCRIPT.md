# Demo Video Script

Target length: 3 to 5 minutes.

## 1. Opening

Introduce the IPO Due Diligence Engine as a deterministic screening tool for
SEBI/NSE/BSE IPO readiness. Emphasize that AI extraction is separate from rule
evaluation.

## 2. Input

Show the upload screen. Use the JSON sample path for a reliable local demo, and
mention that PDF screening follows the same `CompanyData` boundary after
extraction.

## 3. Screening Result

Open the report page. Highlight:

- Overall status: eligible, not eligible, or needs review.
- Mandatory requirements as blocking checks.
- Advisory checks as non-blocking due-diligence warnings.

## 4. Evidence Traceability

Open one mandatory rule result and point to the source document/page citation.
Explain that every extracted value carries provenance through `ExtractedValue`.

## 5. Gap Planner

Use the not-eligible profitability sample. Show failed mandatory rules, gap
size, remediation steps, and earliest eligibility estimate when available.

## 6. Rule Explorer

Open the rules page. Show how rule IDs map to regulation references and how
mandatory/advisory classification is visible without reading source code.

## 7. Close

Summarize the trust boundary: AI extracts, Pydantic validates, deterministic
rules decide, and reports cite evidence.

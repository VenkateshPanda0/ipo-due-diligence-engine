# RedHerring

**A forensic reader for Indian IPO offer documents.** Give it a DRHP, RHP or Prospectus; it gives
back the numbers that matter, each tied to the PDF page it came from, and a short list of
diligence flags with the evidence beside them. Where it cannot be sure, it says nothing rather
than guess.

> Not investment advice. This is automated analysis of public filings. Verify every figure
> against the source document; each one links to its page.

---

## Why it exists

An offer document runs to 400 to 1,500 pages. The facts a reader needs (how much is fresh issue
versus offer for sale, how much of the money is "general corporate purposes", whether profits turn
into cash, whether receivables are outrunning sales) are spread across the cover, the summary, the
objects section and the restated financial statements, often printed several times and sometimes
inconsistently. RedHerring reads all the copies, checks them against each other, and shows its
work.

## What you get

For each filing, `rh report` writes one self-contained HTML page:

- **Issue and objects**: fresh issue, offer for sale, total size, general corporate purposes,
  unidentified acquisitions, debt repayment, monitoring agency, eligibility route (Reg. 6(1) or
  6(2)).
- **Annual figures in ₹ crore**: revenue, total income, profit before and after tax, total assets,
  operating cash flow. Every number links to the PDF page it was read from.
- **Flags with evidence**: what was tested, the figures used, the threshold, and the clause or
  paper behind the threshold.
- **What could not be checked**: missing inputs, withheld figures, pages with hidden text.

`rh diff OLD NEW` compares two versions of one offering (for example a DRHP and its RHP) figure by
figure and shows what changed in issue size, restated numbers and flags.

## How it avoids being confidently wrong

| Principle | What it means in practice |
|---|---|
| **Cite or stay silent** | Every extracted value carries a page number and the text span it came from. After extraction the span is re-read from the PDF; a value that cannot be found on its cited page is discarded. |
| **Cross-check the filing against itself** | A total income that appears in four tables must agree across them. Statement columns are tested for footing (assets = equity + liabilities; total income = revenue + other income; profit = PBT − tax). Disagreement is shown, not resolved by guesswork. |
| **Prefer the issuer's own figures** | Subsidiary and peer statements foot just as well as the issuer's. Readings from the front of the document count more; columns headed "excluding", "standalone" or "subsidiary" count for nothing; a subsidiary figure cannot beat a group figure for size measures. |
| **Abstain when definitions conflict** | Where a filing prints owners' profit in one table and total profit including minority interests in another, the tool declines to pick one. |
| **Thresholds say where they come from** | A regulatory threshold names the SEBI ICDR clause, its effective date and the date it was last checked. A heuristic says it is a heuristic. Rules are not applied to a filing the rule was not in force for, nor to sectors where the test means something else (cash-flow tests skip lenders and developers). |
| **Untrusted input** | Offer documents are treated as hostile text. Text a reader cannot see (tiny, off-page, white on white) is dropped or flagged, and facts resting on it are kept out of the rules. The shipped pipeline is deterministic and uses no language model; an optional LLM layer exists but is untested against a real model, and its output would be re-checked against the PDF. See `docs/security.md`. |

## Red-flag rules

Twelve rules, each a TOML file in `src/redherring/flags/rules/`:

| Area | Rule | Severity |
|---|---|---|
| Financials | Operating cash flow persistently below reported profit | medium |
| Financials | Trade receivables growing much faster than revenue | medium |
| Objects | No monitoring agency although the issue is above the threshold (mainboard, SME, SME before 8 Mar 2025) | high |
| Objects | General corporate purposes close to the regulatory cap (mainboard, SME, SME before 8 Mar 2025) | medium |
| Objects | General corporate purposes plus unidentified acquisitions close to the combined cap | medium |
| Objects | Unidentified acquisitions close to their own cap | medium |
| Objects | More than half of the fresh issue repays borrowings (heuristic) | low |
| Issue | Offer for sale close to the SME limit | medium |

A flag is a prompt to read the cited pages, not a verdict.

## How well does it work?

Measured, not claimed. `rh eval` scores the extractor against 452 hand-labelled fields (367 present,
85 deliberately absent) across 27 filings. The key number is the **first run on filings the tool
had never seen**, with labels committed before the extractor was run:

| Held-out set | Filings | Fields correct (first run) | Wrong | Invented |
|---|---|---|---|---|
| 1 | Indiqube, Laxmi India Finance, Vishal Mega Mart | 31/41 (76%) | 4 | 0/10 |
| 2 | LEAP India, Shiprocket, Indong Tea | 32/42 (76%) | 2 | 0/7 |
| 3 | Powerica, SRIT India, Veritas Finance | 38/39 (97%) | 0 | 0/11 |
| 4 | Lenskart, Tata Capital, PhysicsWallah | 21/39 (54%) | 3 | 3/12 |
| 5 | Zetwerk, Tonbo Imaging, Paras Healthcare | 33/38 (87%) | 1 | 2/13 |
| 6 | Shah Investor's Home, Orient Cables, Nityas Gems | 40/46 (87%) | 0 | 0/12 |
| 7 | Sahajanand Medical, Fusion CX, Swastika Infra | 49/49 (100%) | 0 | 2/11 |

After the defects each set exposed were fixed, all 27 filings together read 362 of 367 present
fields correctly (99%), with none wrong and none invented in 85 absent fields. That second number is
**development accuracy** and will flatter the tool; the first-run column is the honest estimate of
how it will do on your next filing: roughly three fields in four to nine in ten, with the
remainder withheld.

Caveats you should know about:

- A filing stops being held out the moment its failures are fixed, so each set is a one-time
  measurement. Five sets of three is a small, non-random sample.
- Labels were written by an AI reading the PDFs with a different tool; there is no second human
  reader. Three "hallucinations" in sets 4 and 5 turned out to be labeller errors, disclosed in
  `docs/heldout-run-4.md` and `-5.md`.
- Long filings with many subsidiary statements remain the hardest case, and sets 6 and 7 were
  only recent mainboard RHPs: lenders, SME prospectuses and scanned filings are under-tested.

## Quick start

```bash
cd redherring
uv sync
uv run rh --data-dir data ingest        # fetch the filings listed in data/sources.toml (polite, hashed)
uv run rh --data-dir data parse         # PDF -> page-tagged text and tables
uv run rh --data-dir data analyze       # extract, verify, cross-check, run rules
uv run rh --data-dir data report        # HTML per filing in data/reports/
uv run rh --data-dir data diff OLD NEW  # compare two versions of an offering
uv run rh --data-dir data eval --labels-dir labels
```

Add a filing by appending a `[[document]]` entry to `data/sources.toml` with its public URL.
Python 3.12, `uv`, Pydantic v2, pdfplumber and pypdfium2 (permissive licences; PyMuPDF is avoided
because it is AGPL).

## How it works

```
PDF ──► parse ──► extract ──► verify ──► rules ──► report / diff
        │          │           │          │
        │          │           │          └ TOML specs, dated, sector-aware, audited
        │          │           └ re-read cited page; footing identities; cross-table consensus
        │          └ statement lines, issue facts, objects tables, each with page + span
        └ text blocks, ruled and unruled tables, units, column headers, hidden-text defence
```

Source layout: `src/redherring/{ingest,parse,extract,verify,flags,eval}`, with `analyze.py` tying the
stages together and `report_html.py` and `diff.py` producing the outputs.

## Documentation

| | |
|---|---|
| `docs/status.md` | Every current number and known defect |
| `docs/heldout-run-1.md` … `-7.md` | Each held-out run: what failed, why, what changed |
| `docs/decisions.md` | Design decisions and their trade-offs |
| `docs/security.md` | Threat model for untrusted PDFs |
| `docs/roadmap.md` | What is done and what is next |
| `docs/CHARTER.md` | How the project is run |

## Data hygiene

Only public filings are fetched, with robots.txt respected, a per-host rate limit and a descriptive
User-Agent. Source URLs and SHA-256 hashes are recorded; PDFs and parsed outputs are git-ignored.

This folder is independent of the rest of the repository (see `docs/decisions.md` for why, and how
to split it out).

## Licence

MIT (see `LICENSE`).

# IPO Due Diligence Engine — Build Spec

## 1. What this is

A tool that evaluates a private/SME company's readiness for an IPO against
actual SEBI/NSE/BSE listing requirements, using its filings and financials as
input, and produces an evidence-backed pass/fail verdict — not a blended
score.

It automates the first-pass screening work a merchant banker's junior analyst
team does manually when deciding whether a company is even worth pursuing as
an IPO client: checking track record, profitability, governance, promoter
history, and legal/regulatory red flags against the documented eligibility
criteria.

**Motivation:** Merchant bankers and IB teams spend significant analyst time
manually reviewing financial statements, governance disclosures, and
regulatory filings to determine whether a company is ready to pursue an IPO.
This project explores how much of that workflow can be automated while
keeping all regulatory decisions deterministic and evidence-backed.

> **Note (context, not core spec):** the original motivation for this project
> was Zerodha's Category I merchant banker licence application (via Zerodha
> Corporate Advisors Pvt Ltd, filed April 2026, under SEBI review as of
> writing) — investment banking is relationship- and diligence-heavy, and
> nobody there has built this screening workflow yet. This is useful framing
> for a README or demo pitch, but the project itself shouldn't be tied to one
> company or point in time — keep it out of the core spec/architecture.

## 2. Who it helps and how

- **Merchant banks / IB teams**: cuts down analyst hours spent manually
  reading DRHPs and financials to pre-screen candidate companies.
- **Founders/CFOs of private companies**: gives a clear, structured answer to
  "what do we still need to fix before we can list," with reasoning tied to
  specific rules.
- **Recruiters/finance firms evaluating this project**: a live demo on real,
  named companies (IPO-pipeline candidates) is a two-minute proof of
  analytical rigor — not a generic "buy/sell" toy.
- **Founders deciding when to start IPO prep**: the Gap-to-IPO Planner (§4c)
  gives a concrete, quantified answer instead of a vague checklist.

## 3. Core principle: deterministic rules, AI only for extraction

- Eligibility logic, thresholds, and pass/fail calculations are **always
  deterministic, rule-based code** — never left to an LLM to decide.
- AI/LLMs are used **only** for:
  - extracting tables and figures from PDFs (DRHP, financial statements,
    auditor reports)
  - summarizing governance/risk sections
  - flagging litigation or related-party items for a human to review
- This split matters for trust and liability: a screening tool that
  confidently gives a wrong eligibility answer is worse than one that gives no
  answer. The AI never touches the accept/reject logic.

## 3a. Engineering Principles

- Decisions are deterministic.
- Every verdict must be explainable.
- Every numeric value must be traceable to a source.
- AI may extract information but never determine eligibility.
- Every rule is unit-tested.
- Reports are reproducible through versioned rulesets.

**Reliability (non-functional requirement):** a deterministic report
generated from the same company data and the same ruleset version must
always produce identical output. This one property communicates
reproducibility, determinism, and testability together — the qualities
reviewers actually look for.

## 4. Architecture

```
Upload DRHP / financials (PDF)
        ↓
Document Intelligence Layer (parsing, OCR, extraction, classification,
table detection)
        ↓
Structured Company Model (a plain data schema — CompanyData — with no
knowledge of PDFs, JSON, or any input source)
        ↓
Rules Engine (deterministic; operates only on CompanyData)
        ↓
Decision Engine (applies rule outcomes to mandatory/advisory status)
        ↓
Evidence Mapper
        ↓
Report Generator
        ↓
Frontend / Output
```

**Why the split matters:** the Rules Engine should know nothing about PDFs —
it only knows `CompanyData(...)`. That means it can later be fed from manual
JSON, PDF, an API, Excel, or a database without changing a single rule. This
is the core separation-of-concerns decision in the whole system.

Manual JSON input is also supported as a fallback/testing path, but PDF
upload + parsing is the primary, more impressive path.

## 4a. What the report contains

**No fake "readiness score."** A single number (71? 82?) invites the obvious
question "why is Company A 71 and Company B 78?" — and the honest answer is
"arbitrary weighting," which undermines the whole tool's credibility. Instead:

- **IPO Status**: `Eligible` or `Not Eligible` — a direct, defensible
  determination from the Decision Engine, not a blended score.
- **Progress**: e.g. `18 / 22 requirements satisfied` — objective, countable,
  no weighting involved.
- **Mandatory Requirements** (pass/fail, blocking): the actual SEBI ICDR
  eligibility criteria — profitability/track record, minimum public float,
  net worth, etc., evaluated by the Rules Engine against `CompanyData`. Any
  fail here blocks IPO eligibility, full stop.
- **Advisory Checks** (non-blocking, flagged for review): auditor changes,
  high related-party transaction volume, board independence gaps, litigation
  history, etc. These mirror how real due diligence teams separate hard
  eligibility gates from judgment-call risk factors.
- **Observations**: free-form notes/flags surfaced by the AI extraction layer
  that don't map to a specific rule but are worth a human's attention.

## 4b. Evidence Traceability

Every pass/fail verdict must cite exactly where it came from. This is one of
the most credibility-building features and should be treated as a first-class
part of the report, not an afterthought — it's what auditors actually look
for: why → where → what number.

```
Operating Profit — PASS
Source: DRHP Page 143
Extracted value: EBIT ₹18.4 Cr
```

## 4c. Gap-to-IPO Planner

For failed mandatory requirements, don't just say `FAIL`. Quantify the gap and
project a timeline based on current trend:

```
Operating Profit — Required: ₹15 Cr
Current: ₹11.8 Cr
Gap: ₹3.2 Cr
Earliest possible eligibility: FY2028 (at current growth trend)
```

This turns the tool from a pass/fail checker into something genuinely useful
for a company deciding when to start IPO prep.

## 4d. Rule Explorer

Each verdict should also show the actual regulation it's checking against, so
the application teaches the regulation while evaluating it:

```
Rule: SEBI ICDR Regulation 6(1)(a)
Requirement: Average operating profit ≥ ₹15 Cr
Company: ₹18.4 Cr
Status: PASS
```

This is low additional effort once rules are encoded with their source
citation, and it's a strong demo feature.

## 4e. Extensibility

Although v1 targets Indian IPO regulations (SEBI, NSE, BSE), the eligibility
engine is intentionally designed around modular rule sets, making it possible
to support additional jurisdictions in the future without changing the
document extraction pipeline.

## 5. Regulation-change handling — decided approach

We explicitly **rejected** building a fully automated "detect SEBI/NSE/BSE
changes → auto-rewrite rules" system. Reasoning: mapping legal amendment text
("in regulation 6(1)(a), the words X shall be substituted with Y") to code
logic reliably is an unsolved, high-risk problem — a wrong auto-update would
silently corrupt eligibility logic, which is the one failure mode that would
destroy this tool's credibility. It's also invisible in a demo, so it isn't
worth the build cost right now.

**What we're doing instead (cheap, still demonstrates the right instinct):**

1. Every report is tagged with a manually-bumped version string, e.g.
   `ruleset_version: "2026-03"`, so reports remain reproducible against a
   point-in-time ruleset even after rules are later updated.
2. A `CHANGELOG.md` in the repo, manually maintained: e.g. "2026-03: updated
   per ICDR Amendment Regulations 2026, changed X threshold." Takes minutes to
   update whenever SEBI publishes something relevant.
3. **Optional, later:** a simple notification script that periodically checks
   the SEBI circulars page and flags "new circular posted — go check if it
   affects the ruleset." Human-in-the-loop only. It never modifies the rules
   engine itself.

## 6. Build order (phased)

**Phase 1 — Foundations**
- Repository structure
- Pydantic models for `CompanyData` (the structured company schema — no
  knowledge of PDFs or any input source)
- Rule definitions (mandatory + advisory, each citing its source regulation)

**Phase 2 — Rules Engine**
- Deterministic Rules Engine operating only on `CompanyData`
- Unit tests for every rule
- Regression tests using real IPO cases; no rule change is accepted unless
  the full regression suite passes

**Phase 3 — Decisions & Reporting**
- Decision Engine (mandatory/advisory rollup, status, progress count)
- Report Generator
- Evidence Mapper + Rule Explorer

**Phase 4 — Document Intelligence**
- PDF parsing, OCR, table extraction
- Extraction confidence scoring (High / Medium / Low); Low triggers "manual
  confirmation required"
- Versioning + changelog (§5)

**Phase 5 — Polish & Demo**
- Frontend (optional/stretch)
- Demo dataset: 5–10 real, named IPO-pipeline or SME companies
- Documentation and demo video (§11)

## 6a. What to explicitly resist adding

At this stage of the project, resist:

- authentication / multi-user support
- dashboards beyond a simple report view
- notifications
- cloud deployment
- microservices
- Kubernetes
- CI/CD as a spec-level discussion

These belong later if the project evolves into a product. Right now they
would dilute the core idea, which is the deterministic rules engine and
evidence traceability — not infrastructure.

## 7. Suggested tech stack

- Backend: FastAPI, Pydantic, SQLModel/PostgreSQL
- PDF/table extraction: pdfplumber, Camelot, Docling, OCR fallback for scanned
  docs
- AI extraction calls: Anthropic/OpenAI API, used strictly for extraction and
  summarization (see §3)
- Frontend (optional/stretch): React or Next.js + Tailwind, simple charting
  (Chart.js) for the mandatory/advisory breakdown and gap-to-IPO planner
- Tests: Pytest, with regression tests around the Rules Engine specifically
  (this is the part that must never silently break)

## 8. Explicitly out of scope (for this version)

- Full "IPO Intelligence Platform" with 25–40 modules, portfolio dashboards,
  multi-company comparison suites, CI/CD infra, auth systems, etc. — that's a
  multi-month build, not a portfolio-scoped project. See also §6a for the
  specific list of things to resist adding at this stage.
- Fully automated regulation-diffing and rule regeneration (see §5).
- Any investment recommendation, "buy/sell," or thesis language — this tool
  reports readiness/gaps only, to avoid stepping into investment-advisor
  territory.

## 9. Definition of done for v1

- Deterministic eligibility engine works correctly on manually-entered JSON
  for at least 3 test companies with known/verifiable outcomes, with unit
  tests for every rule.
- Mandatory vs advisory checks are clearly separated in output; no blended
  "readiness score" exists anywhere in the system.
- DRHP PDF upload correctly extracts financials (with confidence levels) and
  feeds them into the same engine, producing a matching report.
- Every verdict in the report links back to its source and its regulation
  (Evidence Traceability + Rule Explorer).
- Every report is version-tagged and reproducible.
- Live demo runs cleanly on 5–10 real companies.

## 10. Naming

Working name: **IPO Due Diligence Engine** (previously "SEBI IPO Readiness
Screener" / "IPO Readiness Screener"). This name better reflects the actual
scope: mandatory + advisory checks, evidence-backed verdicts, and gap
planning — closer to a due-diligence workflow than a simple pass/fail
utility. Other options considered: IPO Readiness Engine, IPO Eligibility
Analyzer, IPO Compliance Engine, IPO Qualification Engine.

## 11. Publishing recommendation

Once built, don't just publish the code. Publish three artifacts together:

1. **The project** (code + tests).
2. **A technical write-up** explaining how SEBI regulations were translated
   into deterministic software and why AI is restricted to extraction only.
3. **A 3–5 minute demo video** showing a DRHP upload, the extraction process,
   evidence traceability, mandatory vs. advisory checks, and the final
   verdict.

This combination demonstrates not just that the system was built, but that
its design and engineering tradeoffs can be clearly explained — often more
memorable to reviewers than the repository alone.

## 12. Positioning

When presenting this project (README, resume, interviews), don't frame it as
"a finance project." Frame it as:

> An explainable, deterministic regulatory decision engine with AI-assisted
> document intelligence.

The IPO domain is the context, not the main selling point. What this project
actually demonstrates, broadly applicable across employers:

- translating legal/regulatory text into executable, testable rules
- building a deterministic inference engine with reproducible output
- designing evidence traceability from decision back to source
- separating probabilistic extraction (AI) from deterministic
  decision-making (rules)
- testing a rules engine against real-world cases via regression suites

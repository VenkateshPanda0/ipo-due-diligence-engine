# Baseline Audit — 2026-10-04

Recorded before any code change on branch `claude/kind-faraday-bxc184` at commit
`c669604` (identical to `main`). Working tree was clean.

## Environment

| Item | Value |
|---|---|
| Python | 3.12 (`uv venv --python 3.12 .venv`; system default 3.11 does not satisfy `requires-python >=3.12`) |
| Node / npm | 22.22.0 / 10.9.4 |
| Tesseract | 5.3.4 (installed via apt for this audit; was absent) |
| Poppler (`pdftoppm`) | present |

## Executed baseline

| Command | Result |
|---|---|
| `uv pip install -e ".[dev]"` | OK |
| `pytest -o addopts=""` | **394 passed**, 0 failed, 0 skipped, 5 warnings (3.0 s) — README claim confirmed |
| `ruff check backend/` | clean |
| `mypy backend/app` | clean (73 files) |
| `npm ci && npx next build` (frontend) | builds; 4 routes (`/`, `/upload`, `/rules`, `/report/[id]`) |
| `uvicorn app.main:app --app-dir backend` | starts; `/health` OK; `/screen/json` with `sample_data/companies/eligible-mainboard` → `eligible`; unknown report → 404 envelope; non-PDF bytes posted as PDF → `UNSUPPORTED_DOCUMENT` |

## Defect register (baseline)

Severity: H = high, M = medium, L = low.

| ID | Class | Sev | Location | Observed | Expected / fix |
|---|---|---|---|---|---|
| D1 | Regulatory | H | `rules/mandatory/*.py` | Citations use ICDR **2009** numbering (Reg 26, 32, 36) | ICDR 2018: Reg 6(1)/6(2) eligibility, Reg 14 promoter contribution, Reg 16 lock-in |
| D2 | Regulatory | H | `rules/mandatory/profitability.py` | Average operating profit over "best 3 of preceding 5 years" | Reg 6(1)(b): average ≥ ₹15 Cr over the **preceding three** years, with operating profit in **each** of them |
| D3 | Regulatory | H | `rules/mandatory/issue_size.py` | Issue size ≤ 5× pre-issue net worth, cited as "Reg 26(2)" | Not present in ICDR 2018 (searched consolidated text); remove from current ruleset |
| D4 | Regulatory | H | engine | No Reg 6(2) (QIB ≥ 75 % of net offer, book-built) alternative route; failures of 6(1) reported as NOT_ELIGIBLE | Model the route explicitly |
| D5 | Regulatory | H | `rules/mandatory/float_requirements.py` | Two-tier SCRR 19(2)(b) (≤₹1,600 Cr → 25 %, else 10 %) | SCRR 19(2)(b) substituted by G.S.R. 184(E), 13-Mar-2026 (six tiers) |
| D6 | Regulatory | M | `minimum_capital.py`, `track_record.py` | Exchange criteria labelled as mandatory SEBI rules | Classify as exchange listing criteria; mark source verification status |
| D7 | Regulatory | M | `net_tangible_assets.py` | Monetary-asset proviso (firm commitment to utilise excess; OFS-only exemption) | Verify and model both provisos |
| D8 | Security / integrity | H | `parser/ai_extractor.py` | A `BEGIN_COMPANY_DATA_JSON` block inside uploaded PDF text is trusted as the full `CompanyData`, including confidence and human-confirmation flags | Never trust document-embedded structured payloads |
| D9 | Data integrity | H | `parser/ai_extractor.py` | "profit before tax"/"EBIT" mapped to operating profit; "cash equivalents" to monetary assets; no unit, period or consolidated/standalone detection | Context-aware extraction with explicit normalisation |
| D10 | Data integrity | H | `models/company_data.py` | Every financial field is required, so a partially extracted document cannot be represented (whole extraction fails or must fabricate) | Optional fields with explicit missing status |
| D11 | Security | H | `core/security.py` | Reviewer role taken from self-asserted `X-User-Role` header; non-constant-time key comparison | Server-side key → identity/role mapping; `hmac.compare_digest` |
| D12 | Security | M | `api/routers/screen.py` | Trusts client `content_type`; reads full body before size check; CPU-bound parsing inside `async` handler; no page/time limits | Magic-byte validation, bounded reads, worker thread, limits |
| D13 | Security | M | `api/middleware.py` | Error envelope returns `exc.__dict__` | Return only whitelisted, safe details |
| D14 | Audit | M | `services/review_service.py` | Review completion overwrites record; can be re-completed; no field-level corrections | Append-only events; immutable completion |
| D15 | Docs | M | `.env.example`, `docs/TECH_DEBT.md`, `docs/DOCUMENT_INTELLIGENCE.md`, `reports/storage.py` | LLM keys advertised as required (unused); PostgreSQL `DATABASE_URL` (unused; code reads `REPORT_DATABASE_URL`, SQLite only); "in-memory" claims contradict SQLite default; "LLM-backed extraction" claim | Correct documentation |
| D16 | Config | L | `pyproject.toml` coverage | `ai_extractor.py` omitted "requires live LLM API" (false) | Include in coverage |
| D17 | Feature gap | H | frontend | ~470 LOC; no dashboard, cases, documents, evidence explorer, settings | Build out |
| D18 | Feature gap | H | backend | No case/document entities, no processing lifecycle, no schema migrations | Build out |

## Regulatory sources retrieved during audit

| Source | URL | Retrieved | SHA-256 of PDF |
|---|---|---|---|
| SEBI ICDR Regulations 2018, consolidated, last amended 21-Mar-2026 | https://www.sebi.gov.in/legal/regulations/mar-2026/securities-and-exchange-board-of-india-issue-of-capital-and-disclosure-requirements-regulations-2018-last-amended-on-march-21-2026-_100581.html | 2026-10-04 | `98b627709b65f174f9b86b44d725bf5d0c43da79b80a704cf22ea48c6755bcf6` |
| SEBI LODR Regulations 2015, consolidated, last amended 14-Jul-2026 | https://www.sebi.gov.in/legal/regulations/jul-2026/securities-and-exchange-board-of-india-listing-obligations-and-disclosure-requirements-regulations-2015-last-amended-on-july-14-2026-_102974.html | 2026-10-04 | `f3c187d46aeb15e10d05614400e653086df1799e575ee4e11a49b5d28d5c9b67` |

NSE (`nseindia.com`) and BSE listing-criteria pages returned HTTP 403 to automated
retrieval. SCRR amendment G.S.R. 184(E) could not be retrieved from the e-Gazette;
its content was cross-checked against two independent law-firm summaries only.

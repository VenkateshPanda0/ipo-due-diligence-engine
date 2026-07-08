# IPO Due Diligence Engine

> A deterministic, explainable IPO eligibility engine that evaluates companies against SEBI ICDR, NSE, and BSE listing regulations using codified regulatory rules—not AI-generated decisions.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-black)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-394%20Passing-success)
![Status](https://img.shields.io/badge/Status-Engineering%20Prototype-orange)

---

# Overview

IPO Due Diligence Engine is an explainable regulatory decision engine that automates the first-pass IPO eligibility assessment of a company against publicly documented SEBI ICDR Regulations, NSE, and BSE listing requirements.

Unlike AI-powered "IPO readiness" tools that ask a language model to determine whether a company qualifies for listing, this system separates the problem into two independent stages:

1. **Document Intelligence**
   - Extract structured financial information from documents.
   - Estimate extraction confidence.
   - Route uncertain values to human review.

2. **Deterministic Rules Engine**
   - Evaluate extracted facts against codified regulations.
   - Produce reproducible pass/fail decisions.
   - Explain every decision with evidence and regulatory references.

The objective is **not** to replace merchant bankers or securities lawyers.

The objective is to automate repetitive regulatory screening while making every decision fully explainable.

---

# Why This Exists

Reviewing IPO readiness is repetitive, regulation-heavy work.

Analysts repeatedly answer questions like:

- Does the company satisfy SEBI ICDR Regulation 26?
- Is promoter contribution sufficient?
- Does the company satisfy minimum net tangible asset requirements?
- What exactly is preventing eligibility?

Those answers should not depend on prompting an LLM.

They should be deterministic.

This project encodes those regulations directly into software.

---

# Architecture

```text
                 PDF / JSON
                      │
                      ▼
           Document Intelligence
          (Extraction Only)
                      │
                      ▼
                CompanyData
                      │
                      ▼
        Deterministic Rules Engine
                      │
                      ▼
             Decision Engine
                      │
                      ▼
             IPO Report Generator
                      │
                      ▼
           FastAPI API + Next.js UI
```

**Important principle**

AI (where used) may extract facts.

AI **never** determines IPO eligibility.

Eligibility decisions are always made by deterministic Python code.

---

# Features

## Deterministic Regulatory Rules

The engine implements **16 codified regulatory checks**.

### Mandatory Rules (11)

A failure in **any** mandatory rule results in **Not Eligible**.

- Net Tangible Assets
- Monetary Assets ≤ 50% of Net Tangible Assets
- Average Operating Profit
- Net Worth
- Issue Size
- Track Record
- Minimum Public Offer / Public Float
- Promoter Contribution
- Promoter Lock-in
- Minimum Post-Issue Capital
- Minimum Market Capitalization

### Advisory Rules (5)

These do **not** block eligibility but are surfaced to reviewers.

- Board Independence
- Audit Committee Composition
- Related Party Transactions
- Auditor Qualifications
- Litigation Risk

---

## Explainable Decisions

Every rule contains:

- Applicable regulation
- Regulation clause
- Required threshold
- Actual company value
- Pass / Fail decision
- Gap analysis
- Supporting evidence
- Source citation

There is intentionally **no single readiness score**.

A score hides why a company failed.

The objective is explainability.

---

## Document Intelligence

Current capabilities include:

- PDF parsing
- OCR fallback
- Financial table extraction
- Confidence scoring
- Human-review workflow

The document extraction pipeline is **self-contained** and does not require external API keys or cloud-hosted LLM services in its current implementation.

Document extraction is intentionally isolated from the regulatory engine.

---

## Backend

Built using FastAPI.

Key endpoints include:

```
POST /screen/json
POST /screen/pdf
GET  /rules
GET  /reports/{id}
GET  /health
```

Other features:

- SQLite persistence
- Typed Pydantic models
- OpenAPI documentation
- Deterministic report generation

---

## Frontend

Next.js interface providing:

- JSON submission
- PDF upload
- Rule Explorer
- Report Viewer
- Evidence Panel
- Gap Planner
- Human Review Panel

---

# Example Workflow

```text
Upload DRHP / JSON

        │
        ▼

Extract Financial Information

        │
        ▼

Normalize CompanyData

        │
        ▼

Evaluate 16 Regulatory Rules

        │
        ▼

Generate Explainable IPO Report
```

---

# Current Status

This project should currently be viewed as a **working engineering prototype**.

## Verified

- ✅ 394 automated tests passing
- ✅ Live FastAPI endpoints tested
- ✅ Deterministic rules verified against referenced regulations
- ✅ SQLite persistence verified
- ✅ API integration tests
- ✅ Rules regression tests
- ✅ Mandatory rules have complete branch coverage

---

# Current Limitations

This project intentionally documents its limitations.

## 1. Real DRHP extraction is still evolving

The **JSON workflow is reliable**.

The **PDF workflow is not yet reliable for real SEBI DRHPs**.

Real filings commonly contain:

- transposed financial tables
- inconsistent terminology
- different reporting units (lakhs / millions / crores)

These formats are not yet handled consistently.

Current recommendation:

- Use JSON input for reliable evaluations.
- Treat PDF upload as experimental.

---

## 2. No regulatory sign-off

The implemented rules were verified against publicly available SEBI regulations.

However,

**no securities-law professional has formally validated the implementation.**

Outputs should therefore be treated as:

**Decision Support**

—not—

**Legal Advice**

---

## 3. Frontend

The frontend builds successfully and integrates with the backend but has not yet undergone extensive real-user usability testing.

---

## 4. Production Readiness

Current prototype limitations:

- API-key authentication only
- No role-based access control
- No production deployment
- Limited operational hardening

Suitable for demonstrations and engineering evaluation.

Not yet intended for production use.

---

# Roadmap

## Near Term

- Support transposed financial summary tables
- Improve financial vocabulary matching using real DRHPs
- Detect and normalize reporting units
- Improve confidence scoring
- Partial extraction with human-review workflow
- Validate against multiple real SEBI filings

---

## Medium Term

- Regression suite using real DRHPs
- Frontend usability improvements
- Independent regulatory validation
- Production deployment

---

## Long Term

- Multi-exchange support
- Multi-jurisdiction support
- Rule versioning
- Additional document types

---

# Design Philosophy

Three engineering principles drive this project.

## 1. Deterministic Decisions

Regulatory compliance is implemented using explicit software rules—not prompts.

---

## 2. Explainability

Every decision should answer:

- Which regulation?
- Which threshold?
- Which value?
- Which evidence?
- Why did it pass or fail?

---

## 3. Honest Uncertainty

If extraction confidence is low,

the system should request human review,

not confidently guess.

Incorrect certainty is worse than explicit uncertainty.

---

# Technology Stack

## Backend

- Python 3.12
- FastAPI
- Pydantic
- SQLite
- Pytest

## Frontend

- Next.js
- React
- TypeScript

## Document Intelligence

- PDF Parsing
- OCR
- Confidence Scoring

---

# Repository Structure

```
backend/
frontend/
docs/
sample_data/
scripts/
```

---

# What This Project Is Not

This project is **not**:

- an investment recommendation engine
- an IPO valuation model
- a stock recommendation system
- legal advice
- an AI system that autonomously decides IPO eligibility

---

# License

MIT License

---

# Disclaimer

This repository is an engineering project intended to demonstrate deterministic regulatory automation and document-intelligence techniques.

It does **not** constitute legal advice, regulatory certification, or investment advice.

Final IPO eligibility should always be confirmed by qualified legal and financial professionals.

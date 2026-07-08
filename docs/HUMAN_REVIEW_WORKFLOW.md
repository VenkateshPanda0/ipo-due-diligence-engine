# Human Review Workflow

This project is designed to do most of the screening work while keeping the final decision with a human reviewer.

## Operating Model

1. The system ingests structured JSON or a PDF and normalizes it into `CompanyData`.
2. The deterministic rules engine evaluates the implemented ruleset and creates a machine status: `eligible`, `not_eligible`, or `needs_review`.
3. The report exposes rule-level pass/fail/inconclusive results, evidence citations, gaps, observations, and remediation steps.
4. An authorised reviewer opens a human review record for the report.
5. The reviewer records the final decision: `proceed`, `do_not_proceed`, or `needs_more_information`.
6. The human decision stores reviewer name, rationale, optional conditions, and completion timestamp.

## API Endpoints

- `POST /reviews/reports/{report_id}` opens or returns the review record for a generated report.
- `GET /reviews/{review_id}` returns the current human review state.
- `POST /reviews/{review_id}/decision` records the authorised final decision.

All review endpoints use the same API-key protection as screening endpoints when `API_KEY` is configured.

## Decision Authority

Every screening response and JSON report includes:

- `machine_assessment_only: true`
- `human_review_required: true`
- `decision_authority: "human_reviewer"`

These fields are deliberate guardrails. They make it explicit to API consumers and the frontend that the engine is an initial-screening assistant, not an autonomous compliance decision-maker.

## Trust Boundary

The system can be used for initial screening when the input data, implemented rules, and ruleset version are understood. It should not be trusted as the final authority until:

- the regulation mapping in `docs/REGULATIONS.md` is reviewed by qualified SEBI/listing counsel,
- the validation gate in `docs/REGULATORY_VALIDATION.md` is completed,
- production PDF/OCR extraction is validated against real DRHPs and annual reports,
- persistent audit storage and reviewer access control are implemented,
- each production output is reviewed by an authorised human.

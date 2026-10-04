# Human review workflow

The engine does the repetitive work: extraction, arithmetic and rule checks. Every
judgement stays with people. There are two kinds of review.

## 1. Field review (evidence level)

Extraction opens a **review item** for every value that is not high-confidence: a
value that needs verification, conflicting candidates, a value with no declared unit,
or an OCR value. Each item shows the proposed value, the printed text and unit, the
period, the basis, the page (with a page-image preview), the surrounding context, and
all the candidate values that were considered.

Resolving an item requires the **reviewer** role (or admin).

| Action | Effect | Reason |
|---|---|---|
| Confirm | The value is marked `confirmed_by_human` and becomes reliable for rules. | optional |
| Correct | The value is replaced (`human_corrected`), and the original is kept in history. | **required** |
| Reject | The value is removed from the case data. | **required** |
| Request more evidence | The item stays open, marked as needing evidence. | optional |

Re-processing a document (retry or re-extraction) marks that document's unresolved items
`superseded`, with an event, and opens fresh items from the new run, so a reviewer never
sees duplicates. Superseded items cannot be resolved.

Each action is an append-only `review_item_events` row with the actor and timestamp,
and produces a new immutable case-data version. Extraction never overwrites a value a
human entered, confirmed or corrected.

Rules treat an unconfirmed, unreliable value as `REQUIRES_HUMAN_REVIEW`, never as PASS
or FAIL. The case outcome is then `AWAITING_HUMAN_REVIEW`.

## 2. Report sign-off (decision level)

A screening report is a machine assessment. It always carries
`machine_assessment_only: true`, `human_review_required: true` and
`decision_authority: "human_reviewer"`. A user with the **reviewer** role (or admin)
records the final decision on a report:

* `proceed`, `do_not_proceed` or `needs_more_information`
* the reviewer's name, the rationale (required) and any conditions

Sign-offs are stored as append-only events (`human_review_events`). The current state
is shown together with the full history. The actor comes from the authenticated
principal; a request header cannot claim a role.

## API

| Endpoint | Role |
|---|---|
| `GET /api/v1/review-items?case_id=&status=` | viewer |
| `POST /api/v1/review-items/{id}/resolve` `{action, value?, reason?}` | reviewer |
| `GET /api/v1/reports/{id}/sign-off` | viewer |
| `POST /api/v1/reports/{id}/sign-off` | reviewer |
| Legacy: `POST /reviews/reports/{report_id}` (open) / `POST /reviews/{id}/decision` | any key / reviewer |

## Trust boundary

Do not treat a report as a legal conclusion. Before relying on the system outside
initial screening:

* a qualified securities-law professional reviews the rules
  ([REGULATORY_VALIDATION.md](REGULATORY_VALIDATION.md));
* a person verifies the benchmark answer keys ([BENCHMARK.md](BENCHMARK.md));
* every report is signed off by an authorised reviewer.

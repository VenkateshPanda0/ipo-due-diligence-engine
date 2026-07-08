import { useState } from "react";
import { ipoApi } from "../services/api";
import type { HumanFinalDecision, HumanReviewResponse, ScreeningResponse } from "../types/api";

const decisionLabels: Record<HumanFinalDecision, string> = {
  proceed: "Proceed",
  do_not_proceed: "Do not proceed",
  needs_more_information: "Needs more information",
};

export function HumanReviewPanel({ report }: { report: ScreeningResponse }) {
  const [review, setReview] = useState<HumanReviewResponse | null>(null);
  const [reviewerName, setReviewerName] = useState("");
  const [finalDecision, setFinalDecision] = useState<HumanFinalDecision>("needs_more_information");
  const [rationale, setRationale] = useState("");
  const [conditions, setConditions] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function openReview() {
    setBusy(true);
    setError(null);
    try {
      setReview(await ipoApi.openReview(report.report_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open human review");
    } finally {
      setBusy(false);
    }
  }

  async function completeReview() {
    if (!review) return;
    setBusy(true);
    setError(null);
    try {
      setReview(
        await ipoApi.completeReview(review.review_id, {
          reviewer_name: reviewerName,
          final_decision: finalDecision,
          rationale,
          conditions: conditions
            .split("\n")
            .map((item) => item.trim())
            .filter(Boolean),
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save human decision");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="humanReview">
      <div className="panelHeader">
        <div>
          <h2>Human Review</h2>
          <p className="muted">Machine result: {report.status}. Final decision remains with an authorised reviewer.</p>
        </div>
        {!review && (
          <button type="button" onClick={openReview} disabled={busy}>
            Open Review
          </button>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      {review && (
        <div className="reviewGrid">
          <dl>
            <dt>Review ID</dt>
            <dd>{review.review_id}</dd>
            <dt>Status</dt>
            <dd>{review.status}</dd>
            <dt>Opened</dt>
            <dd>{new Date(review.opened_at).toLocaleString()}</dd>
            {review.completed_at && (
              <>
                <dt>Completed</dt>
                <dd>{new Date(review.completed_at).toLocaleString()}</dd>
              </>
            )}
          </dl>

          {review.status === "completed" ? (
            <div className="reviewDecision">
              <h3>{review.final_decision ? decisionLabels[review.final_decision] : "Decision saved"}</h3>
              <p>{review.rationale}</p>
              {review.conditions.length > 0 && (
                <ul>
                  {review.conditions.map((condition) => (
                    <li key={condition}>{condition}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : (
            <form className="reviewForm" onSubmit={(event) => event.preventDefault()}>
              <label>
                Reviewer
                <input value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} />
              </label>
              <label>
                Final decision
                <select
                  value={finalDecision}
                  onChange={(event) => setFinalDecision(event.target.value as HumanFinalDecision)}
                >
                  {Object.entries(decisionLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Rationale
                <textarea value={rationale} onChange={(event) => setRationale(event.target.value)} />
              </label>
              <label>
                Conditions
                <textarea value={conditions} onChange={(event) => setConditions(event.target.value)} />
              </label>
              <button type="button" onClick={completeReview} disabled={busy}>
                Save Human Decision
              </button>
            </form>
          )}
        </div>
      )}
    </section>
  );
}

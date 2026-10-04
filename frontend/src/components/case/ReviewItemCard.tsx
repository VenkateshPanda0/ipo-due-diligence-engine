import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Badge, ErrorState } from "@/components/ui";
import { PagePreviewButton } from "@/components/report/PagePreview";
import { api } from "@/lib/api";
import { kindForPath } from "@/lib/fields";
import { fieldLabel, fieldStatusLabel, fieldStatusTone, formatDate, formatValue, humanize, unitLabel } from "@/lib/format";
import { validateCorrection } from "@/lib/forms";
import type { TReviewItem } from "@/lib/schemas";

type Candidate = { value?: string | null; raw_value?: string | null; original_text?: string; original_unit?: string | null; page?: number; period_label?: string; basis?: string | null; method?: string; score?: number; context?: string; raw_label?: string };

export function ReviewItemCard({ item, showCase = false }: { item: TReviewItem; showCase?: boolean }) {
  const qc = useQueryClient();
  const kind = kindForPath(item.field_path);
  const [action, setAction] = useState<"confirm" | "correct" | "reject" | "request_more_evidence">("confirm");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [touched, setTouched] = useState(false);
  const shown = item.current ?? item.proposed;
  const canConfirm = !!shown && shown.value !== null && shown.value !== undefined;
  const error = touched ? validateCorrection(action, value, reason, kind) ?? (action === "confirm" && !canConfirm ? "Nothing to confirm — use Correct." : null) : null;
  const resolve = useMutation({
    mutationFn: () =>
      api.resolveItem(item.id, {
        action,
        reason: reason.trim() || undefined,
        value: action === "correct" ? (kind === "bool" ? ["true", "yes"].includes(value.trim().toLowerCase()) : value.trim()) : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-items"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] }); // sidebar open-item count
      qc.invalidateQueries({ queryKey: ["case", item.case_id] });
      qc.invalidateQueries({ queryKey: ["case-data", item.case_id] });
      qc.invalidateQueries({ queryKey: ["documents", item.case_id] });
    },
  });
  const candidates = item.candidates as Candidate[];
  const resolved = item.status !== "open" && item.status !== "more_evidence_requested";

  return (
    <article className="card" aria-label={`Review ${fieldLabel(item.field_path)}`}>
      <div className="card-head">
        <div>
          <h3>{fieldLabel(item.field_path)}</h3>
          <div className="subtle mono">{item.field_path}</div>
        </div>
        <div className="row">
          <Badge tone={fieldStatusTone[item.field_status] ?? "neutral"}>{fieldStatusLabel[item.field_status] ?? humanize(item.field_status)}</Badge>
          <Badge tone={resolved ? "positive" : "attention"} plain>
            {humanize(item.status)}
          </Badge>
          {showCase && <Link href={`/cases/${item.case_id}?tab=review`}>Open case</Link>}
        </div>
      </div>
      <div className="card-body stack">
        <p>{item.reason}</p>
        <div className="grid grid-2">
          <div>
            <div className="subtle">Current / proposed value</div>
            <div style={{ fontSize: 18, fontWeight: 600 }} className="num">
              {shown ? formatValue(shown.value, shown.unit) : "No normalised value"}
            </div>
            {shown && (
              <div className="subtle">
                {shown.original_text && <>Printed as <code>{shown.original_text.length > 60 ? `${shown.original_text.slice(0, 60)}…` : shown.original_text}</code> {shown.original_unit ? `(${unitLabel[shown.original_unit] ?? shown.original_unit})` : ""} · </>}
                {humanize(shown.extraction_method)} · {humanize(shown.confidence)} confidence
                {shown.period_label && <> · {shown.period_label}</>}
                {shown.statement_basis && <> · {humanize(shown.statement_basis)}</>}
              </div>
            )}
            {shown?.page_number && item.document_id && (
              <div style={{ marginTop: 6 }}>
                <PagePreviewButton documentId={item.document_id} page={shown.page_number} snippet={shown.raw_text ?? undefined} />
              </div>
            )}
          </div>
          <div>
            <div className="subtle">Source context</div>
            {shown?.raw_text ? <div className="snippet">{shown.raw_text}</div> : <p className="muted">No context recorded.</p>}
          </div>
        </div>
        {candidates.length > 0 && (
          <details>
            <summary>{candidates.length} candidate value(s) considered</summary>
            <div className="table-wrap" style={{ marginTop: 8 }}>
              <table className="data">
                <thead>
                  <tr>
                    <th>Value (₹ Cr)</th>
                    <th>As printed</th>
                    <th>Period</th>
                    <th>Basis</th>
                    <th className="num">Page</th>
                    <th>Method</th>
                    <th className="num">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c, i) => (
                    <tr key={i}>
                      <td className="num">{c.value ?? <span className="subtle">unit unknown ({c.raw_value})</span>}</td>
                      <td className="mono">{c.original_text} {c.original_unit ? unitLabel[c.original_unit] ?? c.original_unit : ""}</td>
                      <td>{c.period_label}</td>
                      <td>{humanize(c.basis)}</td>
                      <td className="num">{c.page}</td>
                      <td>{humanize(c.method)}</td>
                      <td className="num">{c.score?.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
        {!resolved ? (
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault();
              setTouched(true);
              if (!validateCorrection(action, value, reason, kind) && !(action === "confirm" && !canConfirm)) resolve.mutate();
            }}
          >
            <fieldset>
              <legend>Decision</legend>
              <div className="row">
                {(["confirm", "correct", "reject", "request_more_evidence"] as const).map((a) => (
                  <label key={a} className="row" style={{ gap: 4 }}>
                    <input type="radio" name={`action-${item.id}`} checked={action === a} onChange={() => setAction(a)} style={{ width: "auto", minHeight: 0 }} />
                    {a === "confirm" ? "Confirm value" : a === "correct" ? "Correct value" : a === "reject" ? "Reject (remove)" : "Request more evidence"}
                  </label>
                ))}
              </div>
            </fieldset>
            {action === "correct" && (
              <label className="field">
                <span>
                  Corrected value <span className="req">*</span>{" "}
                  <span className="subtle">{kind === "bool" ? "(yes / no)" : kind === "int" ? "(whole number)" : item.field_path.startsWith("financials") ? "(₹ crore)" : "(number)"}</span>
                </span>
                <input value={value} onChange={(e) => setValue(e.target.value)} inputMode={kind === "bool" ? "text" : "decimal"} />
              </label>
            )}
            <label className="field">
              <span>
                Reason {action === "correct" || action === "reject" ? <span className="req">*</span> : <span className="subtle">(optional)</span>}
              </span>
              <textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={2000} placeholder="e.g. Verified against DRHP p. 312, restated consolidated summary." />
            </label>
            {error && <span className="field-error" role="alert">{error}</span>}
            {resolve.isError && <ErrorState error={resolve.error} />}
            <div>
              <button className="btn btn-primary" type="submit" disabled={resolve.isPending}>
                {resolve.isPending ? "Saving…" : "Record decision"}
              </button>
            </div>
          </form>
        ) : null}
        {item.history.length > 0 && (
          <details>
            <summary>History ({item.history.length})</summary>
            <ul className="tight" style={{ marginTop: 6 }}>
              {item.history.map((h, i) => (
                <li key={i}>
                  <strong>{humanize(String(h.action))}</strong> by {String(h.actor)} · {formatDate(String(h.created_at))}
                  {h.reason ? <> — “{String(h.reason)}”</> : null}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </article>
  );
}

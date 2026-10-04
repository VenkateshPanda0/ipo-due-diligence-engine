import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Card, ErrorState, LoadingBlock, Modal, Notice } from "@/components/ui";
import { api } from "@/lib/api";
import { FISCAL_FIELDS, SCALAR_GROUPS, getPath } from "@/lib/fields";
import { fieldStatusLabel, formatDate, formatValue, humanize, unitLabel } from "@/lib/format";
import { validateFieldValue, type FieldKind } from "@/lib/forms";
import type { TExtractedValue } from "@/lib/schemas";

type EV = TExtractedValue | null | undefined;

function sourceTone(ev: EV): { tone: "positive" | "info" | "attention" | "neutral"; label: string } {
  if (!ev) return { tone: "neutral", label: "Missing" };
  if (ev.extraction_method === "manual") return { tone: "info", label: "Manual" };
  if (ev.confirmed_by_human || ev.extraction_method === "human_corrected") return { tone: "positive", label: "Reviewer" };
  if (ev.field_status && ev.field_status !== "extracted_high_confidence") return { tone: "attention", label: fieldStatusLabel[ev.field_status] ?? humanize(ev.field_status) };
  return { tone: "positive", label: "Extracted" };
}

function ValueCell({ ev, onEdit }: { ev: EV; onEdit: () => void }) {
  const s = sourceTone(ev);
  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="num" style={{ fontWeight: 500 }}>{ev ? formatValue(ev.value, ev.unit) : <span className="subtle">—</span>}</span>
        <button className="btn btn-sm btn-ghost" onClick={onEdit} aria-label="Edit value">
          Edit
        </button>
      </div>
      <div className="row" style={{ gap: 4 }}>
        <Badge tone={s.tone} plain>{s.label}</Badge>
        {ev?.page_number ? <span className="subtle">p.{ev.page_number}</span> : null}
      </div>
    </div>
  );
}

export function FactsPanel({ caseId, editable }: { caseId: string; editable: boolean }) {
  const data = useQuery({ queryKey: ["case-data", caseId], queryFn: () => api.caseData(caseId) });
  const [edit, setEdit] = useState<null | { path: string; label: string; kind: FieldKind; ev: EV; periodEnd?: string }>(null);
  const [newYear, setNewYear] = useState("");
  if (data.isLoading) return <LoadingBlock rows={8} />;
  if (data.isError) return <ErrorState error={data.error} onRetry={() => data.refetch()} />;
  const payload = data.data?.payload ?? {};
  const years = ((getPath(payload, "financials.fiscal_years") as Record<string, unknown>[] | undefined) ?? []).filter(Boolean);
  const basis = getPath(payload, "financials.statement_basis") as string | undefined;
  const open = (path: string, label: string, kind: FieldKind, ev: EV, periodEnd?: string) => editable && setEdit({ path, label, kind, ev, periodEnd });

  return (
    <div className="stack">
      <Notice tone="neutral">
        Data version <strong>{data.data?.version}</strong> ({humanize(data.data?.source)}{data.data?.reason ? ` — ${data.data.reason}` : ""}) by {data.data?.created_by} on {formatDate(data.data?.created_at)}. Every
        change creates a new version; screenings record the version they used.
      </Notice>
      <Card
        title="Financial history (₹ crore, restated)"
        actions={
          editable && (
            <form
              className="row"
              onSubmit={(e) => {
                e.preventDefault();
                const y = Number(newYear);
                if (y >= 1990 && y <= 2100) {
                  setEdit({ path: `financials.fiscal_years[FY${y}].net_worth`, label: `Net worth · FY${y}`, kind: "decimal", ev: null, periodEnd: `${y}-03-31` });
                  setNewYear("");
                }
              }}
            >
              <input aria-label="Add fiscal year (year ending 31 March)" placeholder="Add FY (e.g. 2025)" value={newYear} onChange={(e) => setNewYear(e.target.value)} style={{ width: 160 }} inputMode="numeric" />
              <button className="btn btn-sm" type="submit">
                Add year
              </button>
            </form>
          )
        }
      >
        {basis && <p className="subtle" style={{ marginBottom: 8 }}>Statement basis: {humanize(basis)}</p>}
        {years.length === 0 ? (
          <p className="muted">No financial periods yet. Upload documents or add a fiscal year to enter values manually.</p>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Field</th>
                  {years.map((y) => (
                    <th key={String(y.year_label)}>
                      {String(y.year_label)}
                      {y.months !== 12 && <div className="subtle">{String(y.months)}-month period</div>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {FISCAL_FIELDS.map((f) => (
                  <tr key={f.key}>
                    <td>
                      {f.label}
                      {f.critical && <div className="subtle">Used by Reg 6(1)</div>}
                    </td>
                    {years.map((y) => {
                      const label = String(y.year_label);
                      const ev = y[f.key] as EV;
                      return (
                        <td key={label} style={{ minWidth: 150 }}>
                          <ValueCell ev={ev} onEdit={() => open(`financials.fiscal_years[${label}].${f.key}`, `${f.label} · ${label}`, "decimal", ev, y.period_end as string | undefined)} />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {SCALAR_GROUPS.map((g) => (
        <Card key={g.title} title={g.title}>
          <div className="table-wrap">
            <table className="data">
              <tbody>
                {g.fields.map((f) => {
                  const ev = getPath(payload, f.path) as EV;
                  return (
                    <tr key={f.path}>
                      <td style={{ width: "50%" }}>{f.label}</td>
                      <td>
                        <ValueCell ev={ev} onEdit={() => open(f.path, f.label, f.kind, ev)} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
      {edit && <EditDialog caseId={caseId} target={edit} onClose={() => setEdit(null)} />}
    </div>
  );
}

function EditDialog({ caseId, target, onClose }: { caseId: string; target: { path: string; label: string; kind: FieldKind; ev: EV; periodEnd?: string }; onClose: () => void }) {
  const qc = useQueryClient();
  const [value, setValue] = useState(target.ev ? String(target.ev.value) : "");
  const [note, setNote] = useState("");
  const [touched, setTouched] = useState(false);
  const error = touched ? validateFieldValue(target.kind, value) : null;
  const save = useMutation({
    mutationFn: (clear: boolean) =>
      api.setFields(caseId, [
        {
          field_path: target.path,
          value: clear ? null : target.kind === "bool" ? ["true", "yes"].includes(value.trim().toLowerCase()) : value.trim(),
          note: note.trim() || undefined,
          period_end: target.periodEnd,
        },
      ]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["case-data", caseId] });
      qc.invalidateQueries({ queryKey: ["case", caseId] });
      onClose();
    },
  });
  const ev = target.ev;
  return (
    <Modal title={`Edit — ${target.label}`} onClose={onClose}>
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          setTouched(true);
          if (!validateFieldValue(target.kind, value)) save.mutate(false);
        }}
      >
        {ev && ev.extraction_method !== "manual" && (
          <Notice tone="caution" title="This value came from a document">
            Saving creates a new data version marked as a manual entry. The extracted value ({formatValue(ev.value, ev.unit)}, p.{ev.page_number ?? "?"}
            {ev.original_text ? `, printed “${ev.original_text}” ${ev.original_unit ? unitLabel[ev.original_unit] ?? "" : ""}` : ""}) stays in the version history. Prefer the review workspace for corrections that need a reviewer.
          </Notice>
        )}
        <label className="field">
          <span>
            Value <span className="req">*</span>{" "}
            <span className="subtle">{target.kind === "bool" ? "yes / no" : target.kind === "int" ? "whole number" : target.path.startsWith("financials") || target.path.includes("size") || target.path.includes("capital") || target.path.includes("cap") || target.path.includes("value") || target.path.includes("exposure") ? "₹ crore" : "number"}</span>
          </span>
          {target.kind === "bool" ? (
            <select value={value} onChange={(e) => setValue(e.target.value)} aria-invalid={!!error}>
              <option value="">Select…</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          ) : (
            <input value={value} onChange={(e) => setValue(e.target.value)} aria-invalid={!!error} inputMode="decimal" autoFocus />
          )}
          {error && <span className="field-error">{error}</span>}
        </label>
        <label className="field">
          <span>
            Source / note <span className="subtle">(optional)</span>
          </span>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. DRHP p. 287, restated consolidated" maxLength={1000} />
        </label>
        {ev && ev.notes && ev.notes.length > 0 && (
          <details>
            <summary>Provenance notes</summary>
            <ul className="tight">
              {ev.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </details>
        )}
        {save.isError && <ErrorState error={save.error} />}
        <div className="row">
          <button className="btn btn-primary" type="submit" disabled={save.isPending}>
            Save new version
          </button>
          {ev && (
            <button className="btn btn-danger" type="button" onClick={() => save.mutate(true)} disabled={save.isPending}>
              Clear value
            </button>
          )}
          <button className="btn" type="button" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}


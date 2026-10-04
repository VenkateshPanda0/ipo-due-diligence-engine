import { Badge } from "@/components/ui";
import { evidenceKindLabel, fieldLabel, formatValue, humanize, legalCategoryLabel, verdictLabel, verdictTone, verificationLabel } from "@/lib/format";
import type { TEvidence, TRuleResult } from "@/lib/schemas";
import { PagePreviewButton } from "./PagePreview";

export type DocResolver = (sha: string | null | undefined) => string | undefined;

export function EvidenceRow({ e, resolveDoc }: { e: TEvidence; resolveDoc?: DocResolver }) {
  const docId = resolveDoc?.(e.document_id);
  return (
    <tr>
      <td title={e.field_path}>{fieldLabel(e.field_path)}</td>
      <td className="num">{formatValue(e.value, e.unit)}</td>
      <td>
        <Badge tone={e.kind === "calculated" ? "info" : e.kind === "reviewer" ? "positive" : e.kind === "manual" ? "neutral" : e.reliable === false ? "attention" : "positive"} plain>
          {evidenceKindLabel[e.kind] ?? e.kind}
        </Badge>
        {e.reliable === false && <div className="field-error">Not yet reliable</div>}
      </td>
      <td>
        {e.kind === "calculated" ? (
          <span className="subtle">Computed from the inputs above</span>
        ) : (
          <>
            {e.source_document ?? "—"}
            {e.page_number ? `, p. ${e.page_number}` : ""}
            {e.original_text && (
              <div className="subtle">
                Printed: <code>{e.original_text}</code> {e.original_unit ? humanize(e.original_unit.replace("INR_", "₹ ").toLowerCase()) : ""}
              </div>
            )}
            {e.period_label && <div className="subtle">{e.period_label}{e.statement_basis ? ` · ${humanize(e.statement_basis)}` : ""}</div>}
          </>
        )}
      </td>
      <td>{docId && e.page_number ? <PagePreviewButton documentId={docId} page={e.page_number} snippet={e.raw_text ?? undefined} label="View" /> : null}</td>
    </tr>
  );
}

export function RuleResultItem({ r, resolveDoc, defaultOpen = false }: { r: TRuleResult; resolveDoc?: DocResolver; defaultOpen?: boolean }) {
  return (
    <details className="rule" open={defaultOpen} id={`rule-${r.rule_id}`}>
      <summary>
        <div>
          <strong>{r.rule_name || r.description}</strong>
          <div className="subtle">
            <code>{r.rule_id}</code>
            {r.rule_version ? ` v${r.rule_version}` : ""} · {r.regulation_reference}
          </div>
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          {r.requires_human_review && r.verdict !== "requires_human_review" && <Badge tone="attention" plain>Review flagged</Badge>}
          <Badge tone={verdictTone[r.verdict]}>{verdictLabel[r.verdict]}</Badge>
        </div>
      </summary>
      <div className="rule-body">
        <p>{r.explanation}</p>
        <div className="kv">
          <div>Required condition</div>
          <div>{r.required_value}</div>
          <div>Observed</div>
          <div className="num">{r.actual_value ?? "—"}</div>
          {r.gap && (
            <>
              <div>Gap</div>
              <div>{r.gap}</div>
            </>
          )}
          <div>Classification</div>
          <div>
            {legalCategoryLabel[r.legal_category ?? ""] ?? humanize(r.legal_category)} · {r.category === "mandatory" ? "can affect outcome" : "advisory only"}
          </div>
          <div>Source verification</div>
          <div>
            <Badge tone={r.verification_status === "primary_text_checked" ? "info" : "caution"} plain>
              {verificationLabel[r.verification_status ?? ""] ?? humanize(r.verification_status)}
            </Badge>{" "}
            {r.source_url && (
              <a href={r.source_url} target="_blank" rel="noopener noreferrer">
                Official source
              </a>
            )}
          </div>
        </div>
        {r.calculation.length > 0 && (
          <div>
            <h4 className="subtle">Calculation</h4>
            <div className="calc">
              {r.calculation.map((c, i) => (
                <div key={i}>{c}</div>
              ))}
            </div>
          </div>
        )}
        {r.missing_inputs.length > 0 && (
          <div className="notice tone-caution">
            <strong>Missing evidence</strong>
            <ul className="tight">
              {r.missing_inputs.map((m) => (
                <li key={m}><code>{m}</code></li>
              ))}
            </ul>
          </div>
        )}
        {r.review_reasons.length > 0 && (
          <div className="notice tone-attention">
            <strong>Human review</strong>
            <ul className="tight">
              {r.review_reasons.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}
        {r.evidence.length > 0 && (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Field</th>
                  <th className="num">Value</th>
                  <th>Kind</th>
                  <th>Source</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {r.evidence.map((e, i) => (
                  <EvidenceRow key={i} e={e} resolveDoc={resolveDoc} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        {r.remediation.length > 0 && (
          <div>
            <h4 className="subtle">Remediation guidance (not a guarantee of eligibility)</h4>
            <ul className="tight">
              {r.remediation.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}
        {r.limitations.length > 0 && (
          <details>
            <summary className="subtle">Known limitations of this rule</summary>
            <ul className="tight">
              {r.limitations.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </details>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { Badge, Card, ErrorState, LoadingBlock } from "@/components/ui";
import { api, type RuleSpec } from "@/lib/api";
import { formatDate, humanize, legalCategoryLabel, routeLabel, verificationLabel } from "@/lib/format";

export default function RulesPage() {
  const rules = useQuery({ queryKey: ["rules"], queryFn: api.rules });
  const rulesets = useQuery({ queryKey: ["rulesets"], queryFn: api.rulesets });
  const [category, setCategory] = useState("all");
  const [verification, setVerification] = useState("all");
  const filtered = useMemo(
    () => (rules.data?.rules ?? []).filter((r) => (category === "all" || r.category === category) && (verification === "all" || r.verification_status === verification)),
    [rules.data, category, verification],
  );
  return (
    <AppShell title="Rule explorer">
      <PageHead title="Rule explorer" description="Every rule's legal basis, applicability, decision procedure, thresholds and verification status — from the versioned ruleset, not hard-coded in the UI." />
      <div className="stack">
        {rulesets.data && (
          <Card title="Rulesets">
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Status</th>
                    <th>Effective</th>
                    <th className="num">Rules</th>
                    <th>Legal review</th>
                    <th>Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {rulesets.data.map((rs) => (
                    <tr key={rs.version}>
                      <td><strong>{rs.version}</strong></td>
                      <td><Badge tone={rs.status === "active" ? "positive" : "neutral"}>{humanize(rs.status)}</Badge></td>
                      <td className="subtle">{rs.effective_from}{rs.effective_to ? ` → ${rs.effective_to}` : ""}</td>
                      <td className="num">{rs.rule_count}</td>
                      <td>{rs.legal_review?.confirmed ? <Badge tone="positive">Confirmed</Badge> : <Badge tone="caution">Not reviewed</Badge>}</td>
                      <td className="subtle">{rs.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        <Card
          title={`Rules in ruleset ${rules.data?.ruleset_version ?? ""}`}
          actions={
            <>
              <select aria-label="Filter category" value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: 160 }}>
                <option value="all">All categories</option>
                <option value="mandatory">Mandatory</option>
                <option value="advisory">Advisory</option>
              </select>
              <select aria-label="Filter verification" value={verification} onChange={(e) => setVerification(e.target.value)} style={{ width: 220 }}>
                <option value="all">Any verification</option>
                {Object.entries(verificationLabel).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </>
          }
        >
          {rules.isLoading && <LoadingBlock />}
          {rules.isError && <ErrorState error={rules.error} />}
          {filtered.map((r) => (
            <RuleSpecItem key={r.rule_id} r={r} />
          ))}
        </Card>
      </div>
    </AppShell>
  );
}

function RuleSpecItem({ r }: { r: RuleSpec }) {
  return (
    <details className="rule">
      <summary>
        <div>
          <strong>{r.name}</strong>
          <div className="subtle"><code>{r.rule_id}</code> v{r.rule_version} · {r.instrument}, {r.provision}</div>
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <Badge tone={r.category === "mandatory" ? "info" : "neutral"} plain>{humanize(r.category)}</Badge>
          <Badge tone={r.verification_status === "primary_text_checked" ? "positive" : r.verification_status === "secondary_sources_only" ? "caution" : "negative"}>
            {verificationLabel[r.verification_status] ?? r.verification_status}
          </Badge>
        </div>
      </summary>
      <div className="rule-body">
        <div className="kv">
          <div>Legal category</div>
          <div>{legalCategoryLabel[r.legal_category] ?? r.legal_category}</div>
          <div>Applies to</div>
          <div>{r.routes.map((x) => routeLabel[x] ?? x).join("; ")}</div>
          <div>Applicability</div>
          <div>{r.applicability}</div>
          <div>Condition</div>
          <div>{r.required_value}</div>
          <div>Decision procedure</div>
          <div>{r.decision_procedure}</div>
          <div>Parameters</div>
          <div className="mono">{Object.keys(r.parameters).length ? Object.entries(r.parameters).map(([k, v]) => `${k} = ${v}`).join(", ") : "—"}</div>
          <div>Inputs</div>
          <div className="mono">{r.required_inputs.join(", ")}</div>
          <div>Evidence</div>
          <div>{r.evidence_requirements}</div>
          <div>Effective</div>
          <div>{r.effective_from ?? "not recorded"}{r.effective_to ? ` → ${r.effective_to}` : ""}</div>
        </div>
        {r.limitations.length > 0 && (
          <div className="notice tone-caution">
            <strong>Known limitations</strong>
            <ul className="tight">{r.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
          </div>
        )}
        <div>
          <h4 className="subtle">Sources</h4>
          <ul className="tight">
            {r.sources.map((s) => (
              <li key={s.source_id}>
                {s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a> : s.title}{" "}
                <Badge tone={s.kind === "primary" ? "positive" : s.kind === "secondary" ? "caution" : "neutral"} plain>{humanize(s.kind)}</Badge>
                {s.accessed_on && <span className="subtle"> · accessed {formatDate(s.accessed_on).split(",")[0]}</span>}
                {s.document_sha256 && <div className="subtle mono">sha256 {s.document_sha256}</div>}
                {s.notes && <div className="subtle">{s.notes}</div>}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </details>
  );
}

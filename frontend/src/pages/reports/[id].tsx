import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/router";
import { useMemo, useState } from "react";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { EvidenceRow, RuleResultItem } from "@/components/report/RuleResults";
import { Badge, Card, ErrorState, Field, LoadingBlock, Notice, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { evidenceKindLabel, formatDate, humanize, outcomeLabel, outcomeTone, routeLabel, verdictLabel } from "@/lib/format";
import type { TEvidence, TReport, TVerdict } from "@/lib/schemas";

type TabId = "rules" | "evidence" | "gaps" | "issues" | "signoff";

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ReportPage() {
  const router = useRouter();
  const id = typeof router.query.id === "string" ? router.query.id : "";
  const [tab, setTab] = useState<TabId>("rules");
  const [verdictFilter, setVerdictFilter] = useState<"all" | TVerdict>("all");
  const report = useQuery({ queryKey: ["report", id], queryFn: () => api.getReport(id), enabled: !!id });
  const caseId = report.data?.case_id ?? null;
  const docs = useQuery({ queryKey: ["documents", caseId], queryFn: () => api.caseDocuments(caseId as string), enabled: !!caseId });
  const resolveDoc = useMemo(() => {
    const map = new Map((docs.data ?? []).filter((d) => d.content_retained).map((d) => [d.sha256, d.id]));
    return (sha: string | null | undefined) => (sha ? map.get(sha) : undefined);
  }, [docs.data]);

  if (!id || report.isLoading)
    return (
      <AppShell title="Report">
        <LoadingBlock rows={8} />
      </AppShell>
    );
  if (report.isError || !report.data)
    return (
      <AppShell title="Report">
        <ErrorState error={report.error} onRetry={() => report.refetch()} />
      </AppShell>
    );
  const r = report.data;
  const outcome = r.outcome ?? null;
  const mandatory = r.mandatory_results.filter((x) => verdictFilter === "all" || x.verdict === verdictFilter);
  const exportAs = async (f: "html" | "json" | "text") => download(await api.exportReport(r.report_id, f), `screening-${r.report_id}.${f === "text" ? "txt" : f}`);

  return (
    <AppShell title={`Report — ${r.company_name}`}>
      <PageHead
        title={r.company_name}
        description={
          <span>
            Screening report <code>{r.report_id.slice(0, 8)}</code> · {formatDate(r.evaluated_at)} · Ruleset {r.ruleset_version}
            {caseId && (
              <>
                {" "}· <Link href={`/cases/${caseId}`}>Open case</Link>
              </>
            )}
          </span>
        }
        actions={
          <>
            <button className="btn btn-sm" onClick={() => exportAs("html")}>Export HTML</button>
            <button className="btn btn-sm" onClick={() => exportAs("json")}>JSON</button>
            <button className="btn btn-sm" onClick={() => exportAs("text")}>Text</button>
          </>
        }
      />
      <div className="stack">
        <Card>
          <div className="spread">
            <div>
              <div className="subtle">Screening outcome</div>
              <div style={{ marginTop: 6 }}>
                {outcome ? (
                  <Badge tone={outcomeTone[outcome]}>{outcomeLabel[outcome]}</Badge>
                ) : (
                  <Badge tone="neutral">Legacy report — {humanize(r.status)}</Badge>
                )}
              </div>
            </div>
            <div className="row">
              {(["passed", "failed", "inconclusive", "requires_review", "not_applicable"] as const).map((k) => (
                <div key={k} style={{ textAlign: "center", minWidth: 80 }}>
                  <div style={{ fontSize: 20, fontWeight: 600 }} className="num">
                    {r.mandatory_progress[k] ?? 0}
                  </div>
                  <div className="subtle">{k === "requires_review" ? "Review" : humanize(k)}</div>
                </div>
              ))}
            </div>
          </div>
          <dl className="meta" style={{ marginTop: 14 }}>
            <dt>Listing route</dt>
            <dd>{r.listing_route ? routeLabel[r.listing_route] : "—"}</dd>
            <dt>Engine</dt>
            <dd>{r.engine_version ?? "1.x"}</dd>
            <dt>Input fingerprint</dt>
            <dd className="mono">{r.input_sha256 ?? "—"}</dd>
            <dt>Legal validation</dt>
            <dd>{r.regulatory_validation_confirmed ? "Confirmed for this deployment" : "Not confirmed by a securities-law professional"}</dd>
          </dl>
        </Card>
        <Notice tone="caution" title="Decision support only">
          This is not a legal opinion or a determination of IPO eligibility. “No failure identified” means only that no supported
          mandatory check failed on the evidence provided.
        </Notice>
        <Tabs<TabId>
          value={tab}
          onChange={setTab}
          tabs={[
            { id: "rules", label: "Rule assessment", count: r.mandatory_results.length + r.advisory_results.length },
            { id: "evidence", label: "Evidence register" },
            { id: "gaps", label: "Gap planner", count: r.gap_analysis.length },
            { id: "issues", label: "Unresolved & limitations", count: r.unresolved_issues.length },
            { id: "signoff", label: "Human sign-off" },
          ]}
        />
        {tab === "rules" && (
          <>
            <Card
              title="Mandatory checks"
              actions={
                <select aria-label="Filter by result" value={verdictFilter} onChange={(e) => setVerdictFilter(e.target.value as typeof verdictFilter)} style={{ width: 200 }}>
                  <option value="all">All results</option>
                  {(Object.keys(verdictLabel) as TVerdict[]).map((v) => (
                    <option key={v} value={v}>
                      {verdictLabel[v]}
                    </option>
                  ))}
                </select>
              }
            >
              {mandatory.length === 0 ? <p className="muted">No rules match this filter.</p> : mandatory.map((x) => <RuleResultItem key={x.rule_id} r={x} resolveDoc={resolveDoc} defaultOpen={x.verdict === "fail"} />)}
            </Card>
            <Card title="Advisory findings (never affect the outcome)">
              {r.advisory_results.map((x) => (
                <RuleResultItem key={x.rule_id} r={x} resolveDoc={resolveDoc} />
              ))}
            </Card>
          </>
        )}
        {tab === "evidence" && <EvidenceRegister report={r} resolveDoc={resolveDoc} />}
        {tab === "gaps" && (
          <Card title="Gap planner">
            {r.gap_analysis.length === 0 ? (
              <p className="muted">No mandatory rule failed or lacked evidence.</p>
            ) : (
              <div className="stack">
                {r.gap_analysis.map((g) => (
                  <div key={g.rule_id} className="rule" style={{ padding: 14 }}>
                    <div className="spread">
                      <strong>
                        <a href={`#rule-${g.rule_id}`} onClick={() => setTab("rules")}>{g.rule_id}</a>
                      </strong>
                      {g.verdict && <Badge tone={g.verdict === "fail" ? "negative" : "caution"}>{verdictLabel[g.verdict as TVerdict] ?? g.verdict}</Badge>}
                    </div>
                    <div className="kv" style={{ marginTop: 8 }}>
                      <div>Gap</div>
                      <div>{g.gap_size}</div>
                      <div>Observed</div>
                      <div>{g.current_value}</div>
                      <div>Required</div>
                      <div>{g.required_value}</div>
                      <div>Timing</div>
                      <div>{g.earliest_eligible_fy}</div>
                    </div>
                    <ul className="tight" style={{ marginTop: 8 }}>
                      {g.remediation_steps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                    {g.professional_review_required && <p className="subtle" style={{ marginTop: 6 }}>Requires professional legal / financial review.</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}
        {tab === "issues" && (
          <div className="grid grid-2">
            <Card title="Unresolved issues">
              {r.unresolved_issues.length === 0 ? <p className="muted">None recorded.</p> : <ul className="tight">{r.unresolved_issues.map((x, i) => <li key={i}>{x}</li>)}</ul>}
              {r.observations.length > 0 && (
                <>
                  <h3 style={{ marginTop: 14 }}>Observations</h3>
                  <ul className="tight">{r.observations.map((x, i) => <li key={i}>{x}</li>)}</ul>
                </>
              )}
            </Card>
            <Card title="Limitations">
              <ul className="tight">{(r.limitations.length ? r.limitations : ["Legacy report: limitations not recorded."]).map((x, i) => <li key={i}>{x}</li>)}</ul>
            </Card>
          </div>
        )}
        {tab === "signoff" && <SignOffPanel report={r} />}
      </div>
    </AppShell>
  );
}

function EvidenceRegister({ report, resolveDoc }: { report: TReport; resolveDoc: (sha: string | null | undefined) => string | undefined }) {
  const [kind, setKind] = useState("all");
  const rows = useMemo(() => {
    const seen = new Map<string, TEvidence & { rules: string[] }>();
    for (const r of [...report.mandatory_results, ...report.advisory_results]) {
      for (const e of r.evidence) {
        const key = `${e.field_path}|${e.value}|${e.kind}`;
        const existing = seen.get(key);
        if (existing) existing.rules.push(r.rule_id);
        else seen.set(key, { ...e, rules: [r.rule_id] });
      }
    }
    return [...seen.values()].filter((e) => kind === "all" || e.kind === kind);
  }, [report, kind]);
  return (
    <Card
      title="Evidence register"
      actions={
        <select aria-label="Filter by evidence kind" value={kind} onChange={(e) => setKind(e.target.value)} style={{ width: 240 }}>
          <option value="all">All evidence</option>
          {Object.entries(evidenceKindLabel).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      }
    >
      <p className="subtle" style={{ marginBottom: 10 }}>
        Extracted values, manual entries, reviewer decisions and rule calculations are distinguished. Calculated values are never
        quoted document figures.
      </p>
      {rows.length === 0 ? (
        <p className="muted">No evidence of this kind.</p>
      ) : (
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
              {rows.map((e, i) => (
                <EvidenceRow key={i} e={e} resolveDoc={resolveDoc} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function SignOffPanel({ report }: { report: TReport }) {
  const qc = useQueryClient();
  const current = useQuery({ queryKey: ["signoff", report.report_id], queryFn: () => api.signOff(report.report_id) });
  const [name, setName] = useState("");
  const [decision, setDecision] = useState("needs_more_information");
  const [rationale, setRationale] = useState("");
  const [conditions, setConditions] = useState("");
  const [touched, setTouched] = useState(false);
  const submit = useMutation({
    mutationFn: () =>
      api.submitSignOff(report.report_id, {
        reviewer_name: name.trim(),
        final_decision: decision,
        rationale: rationale.trim(),
        conditions: conditions.split("\n").map((c) => c.trim()).filter(Boolean),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["signoff", report.report_id] }),
  });
  const errors = { name: !name.trim() ? "Reviewer name is required." : null, rationale: !rationale.trim() ? "Rationale is required." : null };
  if (current.isLoading) return <LoadingBlock />;
  if (current.isError) return <ErrorState error={current.error} />;
  const review = current.data?.review as null | { status: string; reviewer_name: string; final_decision: string; rationale: string; conditions: string[]; completed_at: string };
  if (review && review.status === "completed") {
    return (
      <Card title="Human sign-off (immutable)">
        <dl className="meta">
          <dt>Decision</dt>
          <dd><Badge tone="info">{humanize(review.final_decision)}</Badge></dd>
          <dt>Reviewer</dt>
          <dd>{review.reviewer_name}</dd>
          <dt>Recorded</dt>
          <dd>{formatDate(review.completed_at)}</dd>
          <dt>Rationale</dt>
          <dd>{review.rationale}</dd>
          <dt>Conditions</dt>
          <dd>{review.conditions.length ? <ul className="tight">{review.conditions.map((c, i) => <li key={i}>{c}</li>)}</ul> : "—"}</dd>
        </dl>
      </Card>
    );
  }
  return (
    <Card title="Record human sign-off">
      <form
        className="stack"
        style={{ maxWidth: 640 }}
        onSubmit={(e) => {
          e.preventDefault();
          setTouched(true);
          if (!errors.name && !errors.rationale) submit.mutate();
        }}
      >
        <p className="muted">The machine screening is advisory. The final decision is recorded here by a reviewer and cannot be changed afterwards.</p>
        <Field label="Reviewer name" required error={touched ? errors.name : null}>
          <input value={name} onChange={(e) => setName(e.target.value)} aria-invalid={touched && !!errors.name} />
        </Field>
        <Field label="Decision" required>
          <select value={decision} onChange={(e) => setDecision(e.target.value)}>
            <option value="needs_more_information">Needs more information</option>
            <option value="proceed">Proceed</option>
            <option value="do_not_proceed">Do not proceed</option>
          </select>
        </Field>
        <Field label="Rationale" required error={touched ? errors.rationale : null}>
          <textarea value={rationale} onChange={(e) => setRationale(e.target.value)} aria-invalid={touched && !!errors.rationale} />
        </Field>
        <Field label="Conditions" hint="One per line.">
          <textarea value={conditions} onChange={(e) => setConditions(e.target.value)} />
        </Field>
        {submit.isError && <ErrorState error={submit.error} />}
        <div>
          <button className="btn btn-primary" type="submit" disabled={submit.isPending}>
            Record decision
          </button>
        </div>
      </form>
    </Card>
  );
}

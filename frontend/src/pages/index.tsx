import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, humanize, outcomeLabel, outcomeTone } from "@/lib/format";
import type { TOutcome } from "@/lib/schemas";

export default function DashboardPage() {
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard, refetchInterval: 15_000 });
  const d = dash.data;

  return (
    <AppShell title="Dashboard">
      <PageHead
        title="Dashboard"
        description="Screening activity across all cases. Every figure is computed from stored cases, documents and reports."
        actions={
          <Link className="btn btn-primary" href="/cases/new">
            New screening case
          </Link>
        }
      />
      {dash.isLoading && <LoadingBlock rows={6} />}
      {dash.isError && <ErrorState error={dash.error} onRetry={() => dash.refetch()} />}
      {d && (
        <div className="stack">
          <div className="grid grid-4">
            <Stat label="Screening cases" value={d.cases_total} hint={`${d.cases_by_status.archived ?? 0} archived`} />
            <Stat label="Open review items" value={d.open_review_items} hint={`${d.cases_awaiting_review} case(s) awaiting review`} tone={d.open_review_items ? "attention" : undefined} />
            <Stat label="Reports generated" value={d.reports_total} hint={`Ruleset ${d.ruleset_version}`} />
            <Stat
              label="Document failures"
              value={d.documents_failed}
              hint={`${d.documents_processing} currently processing`}
              tone={d.documents_failed ? "negative" : undefined}
            />
          </div>

          {d.cases_total === 0 ? (
            <Card>
              <EmptyState
                title="No screening cases yet"
                action={
                  <Link className="btn btn-primary" href="/cases/new">
                    Create the first case
                  </Link>
                }
              >
                Create a case, upload a DRHP or audited financial statements, review the extracted evidence and run the
                screening.
              </EmptyState>
            </Card>
          ) : (
            <div className="grid grid-2">
              <Card title="Screening outcomes" actions={<Link href="/reports">All reports</Link>}>
                {Object.keys(d.reports_by_outcome).length === 0 ? (
                  <p className="muted">No screenings have been run yet.</p>
                ) : (
                  <table className="data">
                    <tbody>
                      {Object.entries(d.reports_by_outcome).map(([k, v]) => (
                        <tr key={k}>
                          <td>
                            {k in outcomeLabel ? (
                              <Badge tone={outcomeTone[k as TOutcome]}>{outcomeLabel[k as TOutcome]}</Badge>
                            ) : (
                              <Badge tone="neutral">Legacy report</Badge>
                            )}
                          </td>
                          <td className="num">{v}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Card>
              <Card title="Cases by status" actions={<Link href="/cases">All cases</Link>}>
                <table className="data">
                  <tbody>
                    {Object.entries(d.cases_by_status).map(([k, v]) => (
                      <tr key={k}>
                        <td>{humanize(k)}</td>
                        <td className="num">{v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </div>
          )}

          <Card title="Recent activity">
            {d.recent_activity.length === 0 ? (
              <p className="muted">No activity recorded.</p>
            ) : (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Action</th>
                      <th>Actor</th>
                      <th>Case</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.recent_activity.map((a, i) => (
                      <tr key={i}>
                        <td className="subtle">{formatDate(a.ts)}</td>
                        <td>{humanize(a.action.replace(".", " — "))}</td>
                        <td>{a.actor}</td>
                        <td>{a.case_id ? <Link href={`/cases/${a.case_id}`}>Open case</Link> : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </AppShell>
  );
}

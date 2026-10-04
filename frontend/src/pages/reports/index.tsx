import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { Badge, Card, EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, humanize, outcomeLabel, outcomeTone } from "@/lib/format";
import type { TOutcome } from "@/lib/schemas";

export default function ReportsPage() {
  const reports = useQuery({ queryKey: ["reports"], queryFn: api.listReports });
  return (
    <AppShell title="Reports">
      <PageHead title="Screening reports" description="Immutable snapshots. Each report records the ruleset and data version it evaluated." />
      <Card>
        {reports.isLoading && <LoadingBlock />}
        {reports.isError && <ErrorState error={reports.error} onRetry={() => reports.refetch()} />}
        {reports.data?.length === 0 && <EmptyState title="No reports yet">Run a screening from a case to produce a report.</EmptyState>}
        {!!reports.data?.length && (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Outcome</th>
                  <th>Ruleset</th>
                  <th>Generated</th>
                </tr>
              </thead>
              <tbody>
                {reports.data.map((r) => (
                  <tr key={r.report_id}>
                    <td>
                      <Link href={`/reports/${r.report_id}`}>{r.company_name}</Link>
                      <div className="subtle mono">{r.report_id.slice(0, 8)}</div>
                    </td>
                    <td>{r.outcome ? <Badge tone={outcomeTone[r.outcome as TOutcome]}>{outcomeLabel[r.outcome as TOutcome]}</Badge> : <Badge tone="neutral">{humanize(r.legacy_status)}</Badge>}</td>
                    <td>{r.ruleset_version}</td>
                    <td className="subtle">{formatDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </AppShell>
  );
}

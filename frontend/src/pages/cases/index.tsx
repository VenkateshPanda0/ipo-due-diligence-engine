import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { Badge, Card, EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { api } from "@/lib/api";
import { caseStatusLabel, caseStatusTone, formatDate, routeLabel } from "@/lib/format";

export default function CasesPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState(""); // debounced search term sent to the API
  const [status, setStatus] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQuery(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);
  const cases = useQuery({
    queryKey: ["cases", query, status],
    queryFn: () => api.listCases({ q: query, status }),
    placeholderData: (prev) => prev, // keep the current rows while the next page loads
  });

  return (
    <AppShell title="Screening cases">
      <PageHead
        title="Screening cases"
        description="Each case holds the company's evidence, its versioned data and every screening report."
        actions={
          <Link className="btn btn-primary" href="/cases/new">
            New case
          </Link>
        }
      />
      <Card>
        <div className="row" style={{ marginBottom: 14 }}>
          <input aria-label="Search by company name" placeholder="Search company…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 280 }} />
          <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)} style={{ maxWidth: 220 }}>
            <option value="">All statuses</option>
            {Object.entries(caseStatusLabel).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </div>
        {cases.isLoading && <LoadingBlock />}
        {cases.isError && <ErrorState error={cases.error} onRetry={() => cases.refetch()} />}
        {cases.data && cases.data.items.length === 0 && (
          <EmptyState title={q || status ? "No matching cases" : "No cases yet"} action={<Link className="btn" href="/cases/new">Create a case</Link>} />
        )}
        {cases.data && cases.data.items.length > 0 && (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Route</th>
                  <th>Status</th>
                  <th className="num">Documents</th>
                  <th className="num">Open review</th>
                  <th className="num">Reports</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {cases.data.items.map((c) => (
                  <tr key={c.id} className="clickable" onClick={() => router.push(`/cases/${c.id}`)}>
                    <td>
                      <Link href={`/cases/${c.id}`} onClick={(e) => e.stopPropagation()}>
                        {c.company_name}
                      </Link>
                    </td>
                    <td className="subtle">{routeLabel[c.listing_route]}</td>
                    <td>
                      <Badge tone={caseStatusTone[c.status] ?? "neutral"}>{caseStatusLabel[c.status] ?? c.status}</Badge>
                    </td>
                    <td className="num">{c.document_count}</td>
                    <td className="num">{c.open_review_items || "—"}</td>
                    <td className="num">{c.report_count || "—"}</td>
                    <td className="subtle">{formatDate(c.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="subtle" style={{ marginTop: 8 }}>
              {cases.data.total} case(s)
            </p>
          </div>
        )}
      </Card>
    </AppShell>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/router";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { DocumentTable, DocumentUploader } from "@/components/case/Documents";
import { FactsPanel } from "@/components/case/Facts";
import { ReviewItemCard } from "@/components/case/ReviewItemCard";
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, Notice, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { caseStatusLabel, caseStatusTone, formatDate, humanize, outcomeLabel, outcomeTone, routeLabel } from "@/lib/format";
import type { TOutcome } from "@/lib/schemas";

type TabId = "overview" | "documents" | "data" | "review" | "screenings" | "history";

export default function CasePage() {
  const router = useRouter();
  const id = typeof router.query.id === "string" ? router.query.id : "";
  const tab = (typeof router.query.tab === "string" ? router.query.tab : "overview") as TabId;
  const qc = useQueryClient();
  const enabled = !!id;
  // Poll only while documents are being processed; otherwise rely on focus / mutation refetches.
  const kase = useQuery({
    queryKey: ["case", id],
    queryFn: () => api.getCase(id),
    enabled,
    refetchInterval: (q) => (q.state.data?.status === "processing_documents" ? 2000 : false),
  });
  const caps = useQuery({ queryKey: ["capabilities"], queryFn: api.capabilities });
  // Keyed on the case's data version and open-item count so the list refreshes when
  // background extraction or another reviewer changes it.
  const items = useQuery({
    queryKey: ["review-items", id, "all", kase.data?.current_version, kase.data?.open_review_items],
    queryFn: () => api.reviewItems({ case_id: id, status: "" }),
    enabled: enabled && !!kase.data,
  });
  const screenings = useQuery({
    queryKey: ["screenings", id, kase.data?.report_count],
    queryFn: () => api.caseScreenings(id),
    enabled,
  });
  const history = useQuery({ queryKey: ["history", id], queryFn: () => api.caseHistory(id), enabled: enabled && tab === "history" });
  const screen = useMutation({
    mutationFn: () => api.screenCase(id),
    onSuccess: (report) => {
      qc.invalidateQueries({ queryKey: ["screenings", id] });
      qc.invalidateQueries({ queryKey: ["case", id] });
      router.push(`/reports/${report.report_id}`);
    },
  });
  const setTab = (t: TabId) => router.replace({ query: { id, tab: t } }, undefined, { shallow: true });

  if (!id || kase.isLoading) {
    return (
      <AppShell title="Case">
        <LoadingBlock rows={6} />
      </AppShell>
    );
  }
  if (kase.isError || !kase.data) {
    return (
      <AppShell title="Case">
        <ErrorState error={kase.error} onRetry={() => kase.refetch()} />
      </AppShell>
    );
  }
  const c = kase.data;
  const archived = c.status === "archived";
  const openItems = (items.data ?? []).filter((i) => i.status === "open" || i.status === "more_evidence_requested");
  const processing = c.status === "processing_documents";
  const stepsDone = [true, c.document_count > 0, c.document_count > 0 && openItems.length === 0 && !processing, c.report_count > 0];
  const firstOpen = stepsDone.indexOf(false);
  const stepState = (n: number) => (stepsDone[n] ? "done" : n === firstOpen ? "current" : "todo");

  return (
    <AppShell title={c.company_name}>
      <PageHead
        title={c.company_name}
        description={
          <span className="row">
            <Badge tone={caseStatusTone[c.status] ?? "neutral"}>{caseStatusLabel[c.status] ?? c.status}</Badge>
            <span>{routeLabel[c.listing_route]}</span>
            <span className="subtle">Data version {c.current_version}</span>
          </span>
        }
        actions={
          <button className="btn btn-primary" onClick={() => screen.mutate()} disabled={screen.isPending || processing || archived} title={processing ? "Wait for document processing to finish" : undefined}>
            {screen.isPending ? "Screening…" : "Run screening"}
          </button>
        }
      />
      {screen.isError && (
        <div style={{ marginBottom: 16 }}>
          <ErrorState error={screen.error} />
        </div>
      )}
      <ol className="steps" aria-label="Workflow progress" style={{ marginBottom: 18 }}>
        {["1. Company & route", "2. Upload documents", "3. Review evidence", "4. Run screening"].map((s, i) => (
          <li key={s} data-state={stepState(i)}>
            {s}
          </li>
        ))}
      </ol>
      <Tabs<TabId>
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "documents", label: "Documents", count: c.document_count },
          { id: "data", label: "Evidence & data" },
          { id: "review", label: "Review", count: openItems.length },
          { id: "screenings", label: "Screenings", count: c.report_count },
          { id: "history", label: "Audit history" },
        ]}
      />
      {tab === "overview" && (
        <div className="grid grid-2">
          <Card title="Case details">
            <dl className="meta">
              <dt>Company</dt>
              <dd>{c.company_name}</dd>
              <dt>Listing route</dt>
              <dd>{routeLabel[c.listing_route]}</dd>
              <dt>Created</dt>
              <dd>
                {formatDate(c.created_at)} by {c.created_by}
              </dd>
              <dt>Updated</dt>
              <dd>{formatDate(c.updated_at)}</dd>
              <dt>Notes</dt>
              <dd>{c.notes || "—"}</dd>
            </dl>
            {c.listing_route === "sme_chapter_ix" && (
              <div style={{ marginTop: 12 }}>
                <Notice tone="caution" title="Unsupported route">The SME route is outside the supported screening scope.</Notice>
              </div>
            )}
          </Card>
          <Card title="Next step">
            {c.document_count === 0 ? (
              <EmptyState title="Upload evidence" action={<button className="btn btn-primary" onClick={() => setTab("documents")}>Go to documents</button>}>
                Upload the DRHP or audited financial statements, or enter values manually under Evidence &amp; data.
              </EmptyState>
            ) : processing ? (
              <p>Documents are being processed. Extraction progress is shown under Documents.</p>
            ) : openItems.length > 0 ? (
              <EmptyState title={`${openItems.length} value(s) need review`} action={<button className="btn btn-primary" onClick={() => setTab("review")}>Review evidence</button>}>
                Uncertain or conflicting extracted values must be confirmed or corrected before they are relied on.
              </EmptyState>
            ) : (
              <EmptyState title="Ready to screen" action={<button className="btn btn-primary" onClick={() => screen.mutate()} disabled={screen.isPending || archived}>Run screening</button>}>
                Missing facts are reported as insufficient evidence — they are never treated as failures.
              </EmptyState>
            )}
          </Card>
        </div>
      )}
      {tab === "documents" && (
        <div className="stack">
          <Card title="Upload documents">
            <DocumentUploader caseId={id} maxMb={caps.data?.limits.max_upload_size_mb ?? 50} disabled={archived} />
            {caps.data && !caps.data.ocr.available && (
              <div style={{ marginTop: 12 }}>
                <Notice tone="caution" title="OCR unavailable">Scanned pages cannot be read on this server; they will be reported as unreadable.</Notice>
              </div>
            )}
          </Card>
          <Card title="Documents">
            <DocumentTable caseId={id} />
          </Card>
        </div>
      )}
      {tab === "data" && <FactsPanel caseId={id} editable={!archived} />}
      {tab === "review" && (
        <div className="stack">
          {items.isLoading && <LoadingBlock />}
          {items.isError && <ErrorState error={items.error} />}
          {items.data && openItems.length === 0 && <EmptyState title="Nothing awaiting review">All extracted values requiring verification have been resolved.</EmptyState>}
          <section aria-label="Open review items" className="stack">
            {openItems.map((i) => (
              <ReviewItemCard key={i.id} item={i} />
            ))}
          </section>
          {items.data && items.data.length > openItems.length && (
            <details>
              <summary>{items.data.length - openItems.length} resolved item(s)</summary>
              <div className="stack" style={{ marginTop: 12 }}>
                {items.data
                  .filter((i) => !openItems.includes(i))
                  .map((i) => (
                    <ReviewItemCard key={i.id} item={i} />
                  ))}
              </div>
            </details>
          )}
        </div>
      )}
      {tab === "screenings" && (
        <Card title="Screening reports">
          {screenings.isLoading && <LoadingBlock />}
          {screenings.data && screenings.data.length === 0 && <EmptyState title="No screenings yet">Run a screening to evaluate the current data version.</EmptyState>}
          {screenings.data && screenings.data.length > 0 && (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Report</th>
                    <th>Outcome</th>
                    <th>Ruleset</th>
                    <th className="num">Data version</th>
                    <th>By</th>
                    <th>When</th>
                  </tr>
                </thead>
                <tbody>
                  {screenings.data.map((r) => (
                    <tr key={r.report_id}>
                      <td>
                        <Link href={`/reports/${r.report_id}`} className="mono">
                          {r.report_id.slice(0, 8)}
                        </Link>
                      </td>
                      <td>{r.outcome ? <Badge tone={outcomeTone[r.outcome as TOutcome]}>{outcomeLabel[r.outcome as TOutcome]}</Badge> : humanize(r.legacy_status)}</td>
                      <td>{r.ruleset_version}</td>
                      <td className="num">{r.data_version ?? "—"}</td>
                      <td>{r.created_by}</td>
                      <td className="subtle">{formatDate(r.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      {tab === "history" && (
        <Card title="Audit history (append-only)">
          {history.isLoading && <LoadingBlock />}
          {history.data && (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Action</th>
                    <th>Actor</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {history.data.map((h, i) => (
                    <tr key={i}>
                      <td className="subtle">{formatDate(h.ts)}</td>
                      <td>{h.action}</td>
                      <td>{h.actor}</td>
                      <td className="mono subtle">{Object.keys(h.details).length ? JSON.stringify(h.details) : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </AppShell>
  );
}

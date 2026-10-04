import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/router";
import { useMemo, useState } from "react";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { PagePreview } from "@/components/report/PagePreview";
import { Badge, Card, ErrorState, LoadingBlock, Notice, ProgressBar, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { docStatusTone, fieldLabel, fieldStatusLabel, fieldStatusTone, formatBytes, formatDate, formatValue, humanize, unitLabel } from "@/lib/format";

type TabId = "fields" | "pages" | "run";

export default function DocumentPage() {
  const router = useRouter();
  const id = typeof router.query.id === "string" ? router.query.id : "";
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabId>("fields");
  const [status, setStatus] = useState("all");
  const [preview, setPreview] = useState<{ page: number; snippet?: string } | null>(null);
  const doc = useQuery({
    queryKey: ["document", id],
    queryFn: () => api.getDocument(id),
    enabled: !!id,
    refetchInterval: (q) => (["uploaded", "extracting"].includes(q.state.data?.status ?? "") ? 1500 : false),
  });
  const done = !!doc.data && !["uploaded", "extracting"].includes(doc.data.status);
  const extraction = useQuery({ queryKey: ["extraction", id, doc.data?.status], queryFn: () => api.extraction(id), enabled: !!id && done });
  const retry = useMutation({ mutationFn: () => api.retryDocument(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["document", id] }) });
  const remove = useMutation({ mutationFn: () => api.deleteDocumentContent(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["document", id] }) });
  const fields = useMemo(() => (extraction.data?.fields ?? []).filter((f) => status === "all" || f.status === status), [extraction.data, status]);

  if (!id || doc.isLoading)
    return (
      <AppShell title="Document">
        <LoadingBlock rows={6} />
      </AppShell>
    );
  if (doc.isError || !doc.data)
    return (
      <AppShell title="Document">
        <ErrorState error={doc.error} />
      </AppShell>
    );
  const d = doc.data;
  const run = extraction.data?.run;
  const metrics = run?.summary.metrics ?? {};

  return (
    <AppShell title={d.filename}>
      <PageHead
        title={d.filename}
        description={
          <span className="row">
            <Badge tone={docStatusTone[d.status] ?? "neutral"}>{humanize(d.status)}</Badge>
            <span>{humanize(d.doc_type)}</span>
            <Link href={`/cases/${d.case_id}?tab=documents`}>Back to case</Link>
          </span>
        }
        actions={
          <>
            {d.status === "failed" && d.content_retained && (
              <button className="btn" onClick={() => retry.mutate()} disabled={retry.isPending}>Retry processing</button>
            )}
            {d.content_retained && done && (
              <button
                className="btn btn-danger"
                onClick={() => window.confirm("Delete the stored file? Metadata, hash and audit history are kept.") && remove.mutate()}
                disabled={remove.isPending}
              >
                Delete stored file
              </button>
            )}
          </>
        }
      />
      <div className="stack">
        {!done && (
          <Card title="Processing">
            <ProgressBar value={d.progress} label="Extraction progress" />
            <p className="subtle" style={{ marginTop: 6 }}>{humanize(d.stage)} · {d.progress}%</p>
          </Card>
        )}
        {d.status === "failed" && <Notice tone="negative" title={`Processing failed (${d.error_code})`}>{d.error_message}</Notice>}
        {!d.content_retained && <Notice tone="neutral">The stored file has been deleted (retention). Page previews are unavailable; extracted evidence and hashes remain.</Notice>}
        {d.warnings.length > 0 && (
          <Notice tone="caution" title="Warnings">
            <ul className="tight">{d.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
          </Notice>
        )}
        <div className="grid grid-4">
          <Card><div className="subtle">Pages</div><div className="num" style={{ fontSize: 20, fontWeight: 600 }}>{d.page_count ?? "—"}</div><div className="subtle">{metrics.native_pages ?? 0} native · {metrics.ocr_pages ?? 0} OCR · {metrics.unreadable_pages ?? 0} unreadable</div></Card>
          <Card><div className="subtle">Tables found</div><div className="num" style={{ fontSize: 20, fontWeight: 600 }}>{metrics.tables ?? "—"}</div><div className="subtle">{metrics.candidates ?? 0} candidate values</div></Card>
          <Card><div className="subtle">Fields</div><div className="num" style={{ fontSize: 20, fontWeight: 600 }}>{metrics.fields_high ?? 0} high</div><div className="subtle">{metrics.fields_needs_verification ?? 0} verify · {metrics.fields_conflicting ?? 0} conflicts</div></Card>
          <Card><div className="subtle">File</div><div style={{ fontWeight: 600 }}>{formatBytes(d.size_bytes)}</div><div className="subtle mono" title={d.sha256}>{d.sha256.slice(0, 16)}…</div></Card>
        </div>
        <Tabs<TabId> value={tab} onChange={setTab} tabs={[{ id: "fields", label: "Extracted fields", count: extraction.data?.fields.length }, { id: "pages", label: "Pages", count: run?.pages.length }, { id: "run", label: "Run details" }]} />
        {extraction.isError && <ErrorState error={extraction.error} />}
        {tab === "fields" && (
          <Card
            title="Field outcomes"
            actions={
              <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 220 }}>
                <option value="all">All statuses</option>
                {Object.entries(fieldStatusLabel).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            }
          >
            {!done ? <p className="muted">Available after processing.</p> : fields.length === 0 ? <p className="muted">No fields.</p> : (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Status</th>
                      <th className="num">Normalised</th>
                      <th>As printed</th>
                      <th className="num">Page</th>
                      <th>Why</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fields.map((f) => {
                      const s = f.selected as Record<string, string | number | null> | null;
                      const top = (f.candidates[0] ?? {}) as Record<string, unknown>;
                      const page = (s?.page_number as number | undefined) ?? (top.page as number | undefined);
                      return (
                        <tr key={f.field_path}>
                          <td>{fieldLabel(f.field_path)}</td>
                          <td><Badge tone={fieldStatusTone[f.status] ?? "neutral"}>{fieldStatusLabel[f.status] ?? f.status}</Badge></td>
                          <td className="num">{s ? formatValue(s.value, s.unit as string) : "—"}</td>
                          <td className="mono">
                            {String(s?.original_text ?? top.original_text ?? "—")}{" "}
                            {s?.original_unit ? unitLabel[String(s.original_unit)] : top.original_unit ? unitLabel[String(top.original_unit)] : ""}
                          </td>
                          <td className="num">
                            {page && d.content_retained ? (
                              <button className="btn btn-sm btn-ghost" onClick={() => setPreview({ page, snippet: String(s?.raw_text ?? top.context ?? "") })}>
                                {page}
                              </button>
                            ) : (page ?? "—")}
                          </td>
                          <td className="subtle" style={{ maxWidth: 360 }}>{f.reason}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}
        {tab === "pages" && run && (
          <Card title="Per-page processing">
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th className="num">Page</th>
                    <th>Classification</th>
                    <th>Method</th>
                    <th className="num">Characters</th>
                    <th className="num">OCR confidence</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {run.pages.map((p) => (
                    <tr key={p.page}>
                      <td className="num">
                        {d.content_retained ? <button className="btn btn-sm btn-ghost" onClick={() => setPreview({ page: p.page })}>{p.page}</button> : p.page}
                      </td>
                      <td>{humanize(p.kind)}</td>
                      <td>{p.readable ? humanize(p.method) : <Badge tone="negative">Unreadable</Badge>}</td>
                      <td className="num">{p.chars}</td>
                      <td className="num">{p.ocr_mean_conf ?? "—"}</td>
                      <td className="subtle">{[p.rotation ? `rotated ${p.rotation}°` : "", ...p.warnings].filter(Boolean).join("; ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        {tab === "run" && run && (
          <Card title="Reproducibility">
            <dl className="meta">
              <dt>Run ID</dt><dd className="mono">{run.id}</dd>
              <dt>Pipeline</dt><dd>{run.pipeline_version} ({humanize(run.status)})</dd>
              <dt>Uploaded</dt><dd>{formatDate(d.created_at)} · attempts {d.attempts}</dd>
              <dt>Environment</dt><dd className="mono">{Object.entries(run.environment).map(([k, v]) => `${k}=${String(v)}`).join("  ")}</dd>
              <dt>Timing</dt><dd>{metrics.seconds_total ?? "—"} s</dd>
              <dt>Suggestions</dt>
              <dd>
                {run.summary.suggestions && Object.keys(run.summary.suggestions).length ? (
                  <ul className="tight">
                    {Object.entries(run.summary.suggestions).map(([k, v]) => (
                      <li key={k}>{humanize(k)}: <strong>{String(v.value)}</strong> <span className="subtle">(p.{v.page})</span></li>
                    ))}
                  </ul>
                ) : "—"}
              </dd>
            </dl>
          </Card>
        )}
      </div>
      {preview && <PagePreview documentId={id} page={preview.page} snippet={preview.snippet} onClose={() => setPreview(null)} />}
    </AppShell>
  );
}

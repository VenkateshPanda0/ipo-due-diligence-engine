import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState, type DragEvent } from "react";
import { Badge, EmptyState, ErrorState, LoadingBlock, Notice, ProgressBar } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { docStatusTone, formatBytes, formatDate, humanize } from "@/lib/format";
import { validateUpload } from "@/lib/forms";
import type { TDocument } from "@/lib/schemas";

const ACTIVE = new Set(["uploaded", "extracting"]);

export function DocumentUploader({ caseId, maxMb, disabled }: { caseId: string; maxMb: number; disabled?: boolean }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [active, setActive] = useState(false);
  const [results, setResults] = useState<{ name: string; ok: boolean; message: string }[]>([]);
  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      const out: { name: string; ok: boolean; message: string }[] = [];
      for (const file of files) {
        const err = validateUpload(file, maxMb);
        if (err) {
          out.push({ name: file.name, ok: false, message: err });
          continue;
        }
        try {
          const doc = await api.uploadDocument(caseId, file);
          out.push({ name: file.name, ok: true, message: doc.duplicate ? "Already uploaded (identical file) — not processed again." : "Uploaded; extraction started." });
        } catch (e) {
          out.push({ name: file.name, ok: false, message: e instanceof ApiError ? e.message : "Upload failed." });
        }
      }
      return out;
    },
    onSuccess: (out) => {
      setResults(out);
      qc.invalidateQueries({ queryKey: ["case", caseId] });
      qc.invalidateQueries({ queryKey: ["documents", caseId] });
    },
  });

  function onFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    upload.mutate(Array.from(list));
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setActive(false);
    if (!disabled) onFiles(e.dataTransfer.files);
  }

  return (
    <div className="stack">
      <div
        className="dropzone"
        data-active={active}
        onDragOver={(e) => {
          e.preventDefault();
          setActive(true);
        }}
        onDragLeave={() => setActive(false)}
        onDrop={onDrop}
        onClick={() => !disabled && input.current?.click()}
        role="button"
        tabIndex={0}
        aria-disabled={disabled}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !disabled && input.current?.click()}
      >
        <strong>{upload.isPending ? "Uploading…" : "Drop PDFs here or click to choose"}</strong>
        <p className="subtle" style={{ marginTop: 4 }}>
          DRHP / RHP, annual reports or audited financial statements. PDF only, up to {maxMb} MB each. Files are validated by
          content, hashed, and processed locally.
        </p>
        <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => onFiles(e.target.files)} aria-label="Choose PDF files" />
      </div>
      {results.map((r, i) => (
        <Notice key={i} tone={r.ok ? "info" : "negative"} title={r.name}>
          {r.message}
        </Notice>
      ))}
    </div>
  );
}

export function DocumentTable({ caseId }: { caseId: string }) {
  const qc = useQueryClient();
  const docs = useQuery({
    queryKey: ["documents", caseId],
    queryFn: () => api.caseDocuments(caseId),
    refetchInterval: (q) => ((q.state.data ?? []).some((d: TDocument) => ACTIVE.has(d.status)) ? 1500 : false),
  });
  const retry = useMutation({
    mutationFn: (id: string) => api.retryDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", caseId] }),
  });
  if (docs.isLoading) return <LoadingBlock />;
  if (docs.isError) return <ErrorState error={docs.error} onRetry={() => docs.refetch()} />;
  if (!docs.data?.length) return <EmptyState title="No documents uploaded">Upload the offer document or audited financial statements to extract evidence.</EmptyState>;
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            <th>Document</th>
            <th>Type</th>
            <th>Status</th>
            <th className="num">Pages</th>
            <th>Uploaded</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {docs.data.map((d) => (
            <tr key={d.id}>
              <td>
                <Link href={`/documents/${d.id}`}>{d.filename}</Link>
                <div className="subtle mono" title={d.sha256}>
                  sha256 {d.sha256.slice(0, 12)}… · {formatBytes(d.size_bytes)}
                </div>
                {d.warnings.length > 0 && <div className="subtle">{d.warnings.length} warning(s)</div>}
              </td>
              <td>{humanize(d.doc_type)}</td>
              <td style={{ minWidth: 180 }}>
                <Badge tone={docStatusTone[d.status] ?? "neutral"}>{humanize(d.status)}</Badge>
                {ACTIVE.has(d.status) && (
                  <div style={{ marginTop: 6 }}>
                    <ProgressBar value={d.progress} label={`Processing ${d.filename}`} />
                    <div className="subtle">{humanize(d.stage)} · {d.progress}%</div>
                  </div>
                )}
                {d.status === "failed" && <div className="field-error">{d.error_message}</div>}
              </td>
              <td className="num">{d.page_count ?? "—"}</td>
              <td className="subtle">{formatDate(d.created_at)}</td>
              <td>
                {d.status === "failed" && d.content_retained && (
                  <button className="btn btn-sm" onClick={() => retry.mutate(d.id)} disabled={retry.isPending}>
                    Retry
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

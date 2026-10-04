import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { Badge, Card, ErrorState, LoadingBlock, Notice } from "@/components/ui";
import { API_BASE_URL, api } from "@/lib/api";
import { getApiKey, setApiKey } from "@/lib/auth";
import { humanize, routeLabel } from "@/lib/format";

export default function SettingsPage() {
  const qc = useQueryClient();
  const caps = useQuery({ queryKey: ["capabilities"], queryFn: api.capabilities, retry: 0 });
  const me = useQuery({ queryKey: ["me"], queryFn: api.me, retry: 0 });
  const [key, setKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  useEffect(() => setHasKey(!!getApiKey()), []);
  const c = caps.data;

  return (
    <AppShell title="Settings & health">
      <PageHead title="Settings & system health" description={<>API endpoint <code>{API_BASE_URL}</code>. Secrets are never displayed.</>} />
      <div className="stack">
        <Card title="Access">
          <div className="stack" style={{ maxWidth: 560 }}>
            {me.data && (
              <p>
                Signed in as <strong>{me.data.user_id}</strong> ({humanize(me.data.role)}){me.data.authenticated ? "" : " — local single-user mode (no API keys configured on the server)"}.
              </p>
            )}
            {me.isError && <ErrorState error={me.error} />}
            <form
              className="row"
              onSubmit={(e) => {
                e.preventDefault();
                setApiKey(key.trim() || null);
                setHasKey(!!key.trim());
                setKey("");
                qc.invalidateQueries();
              }}
            >
              <input type="password" autoComplete="off" placeholder={hasKey ? "A key is set for this browser tab" : "Paste API key"} value={key} onChange={(e) => setKey(e.target.value)} aria-label="API key" style={{ maxWidth: 320 }} />
              <button className="btn" type="submit">Save for this tab</button>
              {hasKey && (
                <button className="btn btn-ghost" type="button" onClick={() => { setApiKey(null); setHasKey(false); qc.invalidateQueries(); }}>
                  Clear
                </button>
              )}
            </form>
            <p className="subtle">The key is kept in this tab&apos;s session storage only and sent as a Bearer token.</p>
          </div>
        </Card>
        {caps.isLoading && <LoadingBlock />}
        {caps.isError && <ErrorState error={caps.error} onRetry={() => caps.refetch()} />}
        {c && (
          <div className="grid grid-2">
            <Card title="Regulatory scope">
              <dl className="meta">
                <dt>Ruleset</dt>
                <dd>{c.ruleset.version} ({humanize(c.ruleset.status)}), effective {c.ruleset.effective_from}</dd>
                <dt>Supported routes</dt>
                <dd>{c.ruleset.supported_routes.map((r) => routeLabel[r] ?? r).join("; ")}</dd>
                <dt>Unsupported</dt>
                <dd>{c.ruleset.unsupported_routes.map((r) => routeLabel[r] ?? r).join("; ") || "—"}</dd>
                <dt>Legal validation</dt>
                <dd>{c.regulatory_validation_confirmed ? <Badge tone="positive">Confirmed</Badge> : <Badge tone="caution">Not confirmed</Badge>}</dd>
              </dl>
            </Card>
            <Card title="Document processing">
              <dl className="meta">
                <dt>Pipeline</dt>
                <dd>{c.pipeline_version}</dd>
                <dt>Supported input</dt>
                <dd>{c.supported_document_types.join(", ")}</dd>
                <dt>OCR</dt>
                <dd>
                  {c.ocr.available ? <Badge tone="positive">Tesseract {c.ocr.tesseract_version}</Badge> : <Badge tone="negative">Unavailable</Badge>} {!c.ocr.enabled && <Badge tone="caution">Disabled</Badge>}
                  <div className="subtle">Up to {c.ocr.max_ocr_pages} OCR pages per document at {c.ocr.dpi} DPI</div>
                </dd>
                <dt>Limits</dt>
                <dd>{c.limits.max_upload_size_mb} MB · {c.limits.max_pdf_pages} pages · {c.limits.processing_timeout_s}s · {c.limits.upload_rate_per_minute} uploads/min</dd>
              </dl>
            </Card>
            <Card title="Data & security">
              <dl className="meta">
                <dt>Database</dt>
                <dd>{c.database.backend} {c.database.reachable ? <Badge tone="positive">Reachable</Badge> : <Badge tone="negative">Unreachable</Badge>}</dd>
                <dt>Authentication</dt>
                <dd>{c.auth.enabled ? "API keys with server-side roles" : "Local single-user mode"}</dd>
                <dt>Retention</dt>
                <dd>{c.retention.retain_documents ? `Uploaded files retained for ${c.retention.retention_days} days` : "Uploaded files deleted after processing"}</dd>
                <dt>External services</dt>
                <dd>{c.external_services.length ? c.external_services.join(", ") : "None — all processing is local"}</dd>
              </dl>
            </Card>
            <Card title="Limitations">
              <Notice tone="caution">
                Screening covers an explicitly limited subset of Indian main-board IPO requirements. Extraction can be wrong; values
                flagged for review must be verified. Nothing here is legal advice.
              </Notice>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}

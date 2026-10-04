import { useEffect, useId, useRef, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import type { Tone } from "@/lib/format";

export function Badge({ tone = "neutral", children, plain = false, title }: { tone?: Tone; children: ReactNode; plain?: boolean; title?: string }) {
  return (
    <span className={`badge tone-${tone}${plain ? " plain" : ""}`} title={title}>
      {children}
    </span>
  );
}

export function Card({ title, actions, children, className = "", id }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section className={`card ${className}`} id={id} aria-label={typeof title === "string" ? title : undefined}>
      {(title || actions) && (
        <div className="card-head">
          {typeof title === "string" ? <h2>{title}</h2> : title}
          {actions && <div className="row">{actions}</div>}
        </div>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: Tone; title?: string; children?: ReactNode }) {
  return (
    <div className={`notice tone-${tone}`} role={tone === "negative" ? "alert" : "status"}>
      {title && <strong>{title}</strong>}
      {children && <div style={{ marginTop: title ? 4 : 0 }}>{children}</div>}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  return (
    <Notice tone="negative" title={e?.status === 401 ? "Authentication required" : "Something went wrong"}>
      <p>{e ? e.message : error instanceof Error ? error.message : "Unexpected error."}</p>
      {e?.status === 401 && <p className="subtle">Set an API key on the Settings page.</p>}
      {e?.requestId && <p className="subtle">Request ID: <code>{e.requestId}</code></p>}
      {onRetry && (
        <button className="btn btn-sm" style={{ marginTop: 8 }} onClick={onRetry}>
          Retry
        </button>
      )}
    </Notice>
  );
}

export function Skeleton({ height = 16, width = "100%" }: { height?: number; width?: number | string }) {
  return <div className="skeleton" style={{ height, width }} aria-hidden="true" />;
}

export function LoadingBlock({ rows = 4 }: { rows?: number }) {
  return (
    <div className="stack" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} height={18} width={`${90 - i * 8}%`} />
      ))}
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number; label: string }) {
  return (
    <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} aria-label={label}>
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (id: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)} id={`tab-${t.id}`}>
          {t.label}
          {t.count !== undefined && <span className="count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prev?.focus();
    };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} ref={ref}>
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button className="btn btn-sm btn-ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="card-body">{children}</div>
      </div>
    </div>
  );
}

export function Field({ label, hint, error, required, children }: { label: string; hint?: string; error?: string | null; required?: boolean; children: ReactNode }) {
  return (
    <label className="field">
      <span>
        {label} {required ? <span className="req" aria-hidden="true">*</span> : <span className="subtle">(optional)</span>}
      </span>
      {children}
      {hint && <span className="hint">{hint}</span>}
      {error && <span className="field-error" role="alert">{error}</span>}
    </label>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: Tone }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value" style={tone ? { color: `var(--${tone})` } : undefined}>
        {value}
      </div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

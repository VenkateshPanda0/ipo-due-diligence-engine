import { useQuery } from "@tanstack/react-query";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/cases", label: "Screening cases" },
  { href: "/review", label: "Review workspace" },
  { href: "/reports", label: "Reports" },
  { href: "/rules", label: "Rule explorer" },
  { href: "/settings", label: "Settings & health" },
];

export function AppShell({ title, children }: { title: string; children: ReactNode }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 60_000, retry: 0 });
  const review = useQuery({ queryKey: ["review-items", "open-count"], queryFn: () => api.reviewItems({ status: "open" }), retry: 0 });
  const active = (href: string) => (href === "/" ? router.pathname === "/" : router.pathname.startsWith(href));

  return (
    <div className="shell">
      <Head>
        <title>{`${title} · IPO Due Diligence Engine`}</title>
      </Head>
      <a href="#main" className="sr-only">
        Skip to content
      </a>
      <aside className="sidebar" data-open={open} aria-label="Primary">
        <div className="brand">
          <strong>IPO Due Diligence</strong>
          <span>Main-board eligibility screening</span>
        </div>
        <nav className="nav" onClick={() => setOpen(false)}>
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} aria-current={active(n.href) ? "page" : undefined}>
              <span>{n.label}</span>
              {n.href === "/review" && (review.data?.length ?? 0) > 0 && <Badge tone="attention" plain>{review.data?.length}</Badge>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-foot">
          Decision support only. Not legal advice.
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="row">
            <button className="btn btn-sm mobile-nav-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label="Toggle navigation">
              ☰
            </button>
            <span className="muted">{title}</span>
          </div>
          <div className="row">
            {health.isError ? (
              <Badge tone="negative">API unreachable</Badge>
            ) : health.data ? (
              <>
                <Badge tone="info" plain title="Active ruleset version">
                  Ruleset {health.data.ruleset_version}
                </Badge>
                <Badge tone={health.data.database ? "positive" : "negative"}>{health.data.database ? "Database OK" : "Database error"}</Badge>
              </>
            ) : null}
          </div>
        </header>
        <main id="main" className="content">
          {children}
        </main>
      </div>
    </div>
  );
}

export function PageHead({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

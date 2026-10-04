import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState } from "@/components/ui";

export default function NotFound() {
  return (
    <AppShell title="Not found">
      <EmptyState title="Page not found" action={<Link className="btn" href="/">Go to dashboard</Link>}>
        The page you requested does not exist.
      </EmptyState>
    </AppShell>
  );
}

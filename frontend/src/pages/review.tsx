import { useQuery } from "@tanstack/react-query";
import { AppShell, PageHead } from "@/components/layout/AppShell";
import { ReviewItemCard } from "@/components/case/ReviewItemCard";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { api } from "@/lib/api";

export default function ReviewQueuePage() {
  const items = useQuery({ queryKey: ["review-items", "queue"], queryFn: () => api.reviewItems({ status: "open" }) });
  return (
    <AppShell title="Review workspace">
      <PageHead
        title="Review workspace"
        description="Extracted values that are uncertain, conflicting or unit-ambiguous. Confirm, correct (with a reason), reject or request more evidence. Originals are always preserved."
      />
      <div className="stack">
        {items.isLoading && <LoadingBlock rows={6} />}
        {items.isError && <ErrorState error={items.error} onRetry={() => items.refetch()} />}
        {items.data?.length === 0 && <EmptyState title="Queue is empty">No extracted value is waiting for review.</EmptyState>}
        {items.data?.map((i) => (
          <ReviewItemCard key={i.id} item={i} showCase />
        ))}
      </div>
    </AppShell>
  );
}

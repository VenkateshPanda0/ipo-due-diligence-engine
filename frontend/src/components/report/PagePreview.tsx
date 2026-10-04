import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ErrorState, LoadingBlock, Modal } from "@/components/ui";
import { api } from "@/lib/api";

export function PagePreview({ documentId, page, snippet, onClose }: { documentId: string; page: number; snippet?: string; onClose: () => void }) {
  const [current, setCurrent] = useState(page);
  const doc = useQuery({ queryKey: ["document", documentId], queryFn: () => api.getDocument(documentId) });
  const img = useQuery({ queryKey: ["page-image", documentId, current], queryFn: () => api.pageImage(documentId, current), staleTime: Infinity, retry: 0 });
  useEffect(() => () => void (img.data && URL.revokeObjectURL(img.data)), [img.data]);
  const pages = doc.data?.page_count ?? page;
  return (
    <Modal title={`${doc.data?.filename ?? "Document"} — page ${current} of ${pages}`} onClose={onClose}>
      <div className="stack">
        {snippet && (
          <div>
            <div className="subtle">Extracted from this context:</div>
            <div className="snippet">{snippet}</div>
          </div>
        )}
        <div className="row">
          <button className="btn btn-sm" onClick={() => setCurrent((p) => Math.max(1, p - 1))} disabled={current <= 1}>
            ← Previous
          </button>
          <button className="btn btn-sm" onClick={() => setCurrent((p) => Math.min(pages, p + 1))} disabled={current >= pages}>
            Next →
          </button>
          {current !== page && (
            <button className="btn btn-sm btn-ghost" onClick={() => setCurrent(page)}>
              Back to cited page {page}
            </button>
          )}
        </div>
        {img.isLoading && <LoadingBlock rows={8} />}
        {img.isError && <ErrorState error={img.error} />}
        {img.data && <img className="page-image" src={img.data} alt={`Page ${current} of ${doc.data?.filename ?? "document"}`} />}
      </div>
    </Modal>
  );
}

export function PagePreviewButton({ documentId, page, snippet, label }: { documentId: string; page: number; snippet?: string; label?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="btn btn-sm" onClick={() => setOpen(true)}>
        {label ?? `View page ${page}`}
      </button>
      {open && <PagePreview documentId={documentId} page={page} snippet={snippet} onClose={() => setOpen(false)} />}
    </>
  );
}

import type { SourceCitation } from "../types/api";

export function EvidencePanel({ citation }: { citation?: SourceCitation | null }) {
  if (!citation) {
    return <span className="muted">No citation available</span>;
  }
  return (
    <span className="evidence">
      {citation.document_name}, page {citation.page_numbers.join(", ")} · {citation.extraction_method} · {citation.confidence}
    </span>
  );
}

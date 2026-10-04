/** Display helpers. Presentation only — no regulatory computation happens here. */
import { FISCAL_FIELDS } from "./fields";
import type { TOutcome, TVerdict } from "./schemas";

export const verdictLabel: Record<TVerdict, string> = {
  pass: "Pass",
  fail: "Fail",
  inconclusive: "Insufficient evidence",
  requires_human_review: "Human review",
  not_applicable: "Not applicable",
};

export const verdictTone: Record<TVerdict, Tone> = {
  pass: "positive",
  fail: "negative",
  inconclusive: "caution",
  requires_human_review: "attention",
  not_applicable: "neutral",
};

export const outcomeLabel: Record<TOutcome, string> = {
  no_failure_identified: "No failure identified within supported screening scope",
  screening_failure: "Preliminary screening failure under implemented rules",
  awaiting_human_review: "Awaiting human review",
  insufficient_evidence: "Insufficient evidence",
  unsupported_scope: "Unsupported regulatory scope",
};

export const outcomeTone: Record<TOutcome, Tone> = {
  no_failure_identified: "positive",
  screening_failure: "negative",
  awaiting_human_review: "attention",
  insufficient_evidence: "caution",
  unsupported_scope: "neutral",
};

export type Tone = "positive" | "negative" | "caution" | "attention" | "neutral" | "info";

export const routeLabel: Record<string, string> = {
  mainboard_reg6_1: "Main board — ICDR Reg 6(1)",
  mainboard_reg6_2: "Main board — ICDR Reg 6(2) (QIB route)",
  sme_chapter_ix: "SME — ICDR Chapter IX (not supported)",
};

export const caseStatusLabel: Record<string, string> = {
  draft: "Draft",
  processing_documents: "Processing documents",
  awaiting_review: "Awaiting review",
  ready_for_screening: "Ready for screening",
  screened: "Screened",
  archived: "Archived",
};

export const caseStatusTone: Record<string, Tone> = {
  draft: "neutral",
  processing_documents: "info",
  awaiting_review: "attention",
  ready_for_screening: "positive",
  screened: "info",
  archived: "neutral",
};

export const docStatusTone: Record<string, Tone> = {
  uploaded: "info",
  extracting: "info",
  awaiting_review: "attention",
  completed: "positive",
  failed: "negative",
  cancelled: "neutral",
};

export const fieldStatusLabel: Record<string, string> = {
  extracted_high_confidence: "Extracted — high confidence",
  extracted_needs_verification: "Needs verification",
  conflicting_candidates: "Conflicting candidates",
  not_found: "Not found",
  unreadable: "Unreadable",
  unsupported_format: "Unsupported format",
  processing_failed: "Processing failed",
  human_confirmed: "Human confirmed",
  manual_entry: "Manual entry",
};

export const fieldStatusTone: Record<string, Tone> = {
  extracted_high_confidence: "positive",
  extracted_needs_verification: "attention",
  conflicting_candidates: "negative",
  not_found: "neutral",
  unreadable: "negative",
  human_confirmed: "positive",
  manual_entry: "info",
};

export const verificationLabel: Record<string, string> = {
  primary_text_checked: "Primary text checked (not legal sign-off)",
  secondary_sources_only: "Secondary sources only",
  unverified: "Unverified",
  legal_reviewed: "Legal reviewed",
};

export const legalCategoryLabel: Record<string, string> = {
  statutory_eligibility: "Statutory eligibility",
  statutory_issue_condition: "Statutory issue condition",
  exchange_listing_criterion: "Exchange listing criterion",
  post_listing_obligation: "Post-listing obligation",
  diligence_indicator: "Diligence indicator",
};

export const evidenceKindLabel: Record<string, string> = {
  extracted: "Extracted from document",
  manual: "Entered manually",
  reviewer: "Reviewer confirmed / corrected",
  calculated: "Calculated by rule",
};

export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export function fieldLabel(path: string): string {
  const fy = /^financials\.fiscal_years\[(.+)\]\.(.+)$/.exec(path);
  if (fy) return `${FISCAL_FIELDS.find((f) => f.key === fy[2])?.label ?? humanize(fy[2])} · ${fy[1]}`;
  const parts = path.split(".");
  return parts.map((p) => humanize(p)).join(" › ");
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export function formatValue(value: unknown, unit?: string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const s = String(value);
  if (unit === "INR_CRORE" && /^-?\d+(\.\d+)?$/.test(s)) {
    const n = Number(s);
    return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 4 })} Cr`;
  }
  if (unit === "PERCENT") return `${s}%`;
  if (unit === "MONTHS") return `${s} months`;
  return s;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export const unitLabel: Record<string, string> = {
  INR: "₹",
  INR_THOUSAND: "₹ thousand",
  INR_LAKH: "₹ lakh",
  INR_MILLION: "₹ million",
  INR_CRORE: "₹ crore",
  INR_BILLION: "₹ billion",
};

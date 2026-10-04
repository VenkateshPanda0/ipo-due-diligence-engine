/**
 * Runtime schemas for API responses the UI depends on.
 *
 * Critical payloads (reports, cases, documents, review items) are validated with
 * zod so a backend contract change fails loudly instead of rendering silently
 * wrong data. Schemas use passthrough() to tolerate additive backend fields.
 */
import { z } from "zod";

export const Verdict = z.enum(["pass", "fail", "inconclusive", "requires_human_review", "not_applicable"]);
export const Outcome = z.enum([
  "no_failure_identified",
  "screening_failure",
  "awaiting_human_review",
  "insufficient_evidence",
  "unsupported_scope",
]);
export const ListingRoute = z.enum(["mainboard_reg6_1", "mainboard_reg6_2", "sme_chapter_ix"]);

export const Evidence = z
  .object({
    field_path: z.string(),
    value: z.string(),
    unit: z.string().nullable().optional(),
    kind: z.string(),
    source_document: z.string().nullable().optional(),
    document_id: z.string().nullable().optional(),
    page_number: z.number().nullable().optional(),
    extraction_method: z.string().nullable().optional(),
    confidence: z.string().nullable().optional(),
    confirmed_by_human: z.boolean().optional(),
    field_status: z.string().nullable().optional(),
    raw_text: z.string().nullable().optional(),
    original_text: z.string().nullable().optional(),
    original_unit: z.string().nullable().optional(),
    period_label: z.string().nullable().optional(),
    statement_basis: z.string().nullable().optional(),
    reliable: z.boolean().optional(),
  })
  .passthrough();

export const RuleResult = z
  .object({
    rule_id: z.string(),
    verdict: Verdict,
    category: z.enum(["mandatory", "advisory"]),
    regulation_reference: z.string(),
    description: z.string(),
    required_value: z.string(),
    actual_value: z.string().nullable(),
    gap: z.string().nullable(),
    explanation: z.string(),
    rule_name: z.string().default(""),
    rule_version: z.string().nullable().optional(),
    legal_category: z.string().nullable().optional(),
    verification_status: z.string().nullable().optional(),
    source_url: z.string().nullable().optional(),
    applicable: z.boolean().default(true),
    calculation: z.array(z.string()).default([]),
    evidence: z.array(Evidence).default([]),
    missing_inputs: z.array(z.string()).default([]),
    requires_human_review: z.boolean().default(false),
    review_reasons: z.array(z.string()).default([]),
    remediation: z.array(z.string()).default([]),
    limitations: z.array(z.string()).default([]),
  })
  .passthrough();

export const Progress = z
  .object({
    total_rules: z.number(),
    passed: z.number(),
    failed: z.number(),
    inconclusive: z.number(),
    requires_review: z.number().default(0),
    not_applicable: z.number().default(0),
    pass_percentage: z.union([z.string(), z.number()]),
    failed_rule_ids: z.array(z.string()),
  })
  .passthrough();

export const GapItem = z
  .object({
    rule_id: z.string(),
    gap_size: z.string(),
    earliest_eligible_fy: z.string(),
    remediation_steps: z.array(z.string()),
    current_value: z.string(),
    required_value: z.string(),
    verdict: z.string().nullable().optional(),
    professional_review_required: z.boolean().optional(),
  })
  .passthrough();

export const Report = z
  .object({
    report_id: z.string(),
    status: z.enum(["eligible", "not_eligible", "needs_review"]),
    outcome: Outcome.nullable().optional(),
    company_name: z.string(),
    listing_route: ListingRoute.nullable().optional(),
    mandatory_progress: Progress,
    advisory_progress: Progress,
    mandatory_results: z.array(RuleResult),
    advisory_results: z.array(RuleResult),
    gap_analysis: z.array(GapItem),
    observations: z.array(z.string()),
    ruleset_version: z.string(),
    evaluated_at: z.string(),
    engine_version: z.string().nullable().optional(),
    case_id: z.string().nullable().optional(),
    input_sha256: z.string().nullable().optional(),
    unresolved_issues: z.array(z.string()).default([]),
    limitations: z.array(z.string()).default([]),
    regulatory_validation_confirmed: z.boolean().default(false),
  })
  .passthrough();

export const Case = z
  .object({
    id: z.string(),
    company_name: z.string(),
    listing_route: ListingRoute,
    status: z.string(),
    current_version: z.number(),
    notes: z.string().nullable().optional(),
    created_by: z.string(),
    created_at: z.string(),
    updated_at: z.string(),
    document_count: z.number().default(0),
    open_review_items: z.number().default(0),
    report_count: z.number().default(0),
  })
  .passthrough();

export const CaseList = z.object({ items: z.array(Case), total: z.number(), limit: z.number(), offset: z.number() });

export const DocumentInfo = z
  .object({
    id: z.string(),
    case_id: z.string(),
    sha256: z.string(),
    filename: z.string(),
    size_bytes: z.number(),
    page_count: z.number().nullable(),
    doc_type: z.string().nullable(),
    status: z.enum(["uploaded", "extracting", "awaiting_review", "completed", "failed", "cancelled"]),
    stage: z.string().nullable(),
    progress: z.number(),
    error_code: z.string().nullable(),
    error_message: z.string().nullable(),
    warnings: z.array(z.string()),
    quality: z.record(z.unknown()),
    attempts: z.number(),
    pipeline_version: z.string().nullable(),
    created_at: z.string(),
    content_retained: z.boolean(),
    duplicate: z.boolean().optional(),
  })
  .passthrough();

export const ExtractedValueJson = z
  .object({
    value: z.unknown(),
    source_document: z.string(),
    page_number: z.number().nullable().optional(),
    extraction_method: z.string(),
    confidence: z.string(),
    confirmed_by_human: z.boolean().optional(),
    raw_text: z.string().nullable().optional(),
    unit: z.string().nullable().optional(),
    original_text: z.string().nullable().optional(),
    original_unit: z.string().nullable().optional(),
    period_label: z.string().nullable().optional(),
    statement_basis: z.string().nullable().optional(),
    field_status: z.string().nullable().optional(),
    conflicting_values: z.array(z.string()).optional(),
    notes: z.array(z.string()).optional(),
    document_id: z.string().nullable().optional(),
  })
  .passthrough();

export const ReviewItem = z
  .object({
    id: z.string(),
    case_id: z.string(),
    document_id: z.string().nullable(),
    field_path: z.string(),
    reason: z.string(),
    field_status: z.string(),
    status: z.string(),
    proposed: ExtractedValueJson.nullable(),
    current: ExtractedValueJson.nullable(),
    candidates: z.array(z.record(z.unknown())),
    created_at: z.string(),
    resolved_at: z.string().nullable(),
    history: z.array(z.record(z.unknown())),
  })
  .passthrough();

export type TVerdict = z.infer<typeof Verdict>;
export type TOutcome = z.infer<typeof Outcome>;
export type TEvidence = z.infer<typeof Evidence>;
export type TRuleResult = z.infer<typeof RuleResult>;
export type TReport = z.infer<typeof Report>;
export type TCase = z.infer<typeof Case>;
export type TDocument = z.infer<typeof DocumentInfo>;
export type TReviewItem = z.infer<typeof ReviewItem>;
export type TExtractedValue = z.infer<typeof ExtractedValueJson>;

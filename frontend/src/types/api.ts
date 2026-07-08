export type IPOStatus = "eligible" | "not_eligible" | "needs_review";
export type Verdict = "pass" | "fail" | "inconclusive";
export type RuleCategory = "mandatory" | "advisory";
export type HumanReviewStatus = "pending" | "completed";
export type HumanFinalDecision = "proceed" | "do_not_proceed" | "needs_more_information";

export interface EligibilityProgress {
  total_rules: number;
  passed: number;
  failed: number;
  inconclusive: number;
  pass_percentage: string;
  failed_rule_ids: string[];
}

export interface SourceCitation {
  document_name: string;
  page_numbers: number[];
  table_reference?: string | null;
  extraction_method: string;
  confidence: string;
}

export interface RuleResult {
  rule_id: string;
  verdict: Verdict;
  category: RuleCategory;
  regulation_reference: string;
  description: string;
  required_value: string;
  actual_value?: string | null;
  gap?: string | null;
  explanation: string;
  source_citation?: SourceCitation | null;
}

export interface GapAnalysisItem {
  rule_id: string;
  gap_size: string;
  earliest_eligible_fy: string;
  remediation_steps: string[];
  current_value: string;
  required_value: string;
}

export interface ScreeningResponse {
  report_id: string;
  status: IPOStatus;
  company_name: string;
  mandatory_progress: EligibilityProgress;
  advisory_progress: EligibilityProgress;
  mandatory_results: RuleResult[];
  advisory_results: RuleResult[];
  gap_analysis: GapAnalysisItem[];
  observations: string[];
  ruleset_version: string;
  evaluated_at: string;
  machine_assessment_only: boolean;
  human_review_required: boolean;
  decision_authority: string;
}

export interface HumanReviewResponse {
  review_id: string;
  report_id: string;
  machine_status: IPOStatus;
  status: HumanReviewStatus;
  reviewer_name?: string | null;
  final_decision?: HumanFinalDecision | null;
  rationale?: string | null;
  conditions: string[];
  opened_at: string;
  completed_at?: string | null;
}

export interface HumanReviewDecisionRequest {
  reviewer_name: string;
  final_decision: HumanFinalDecision;
  rationale: string;
  conditions: string[];
}

export interface RuleDetail {
  rule_id: string;
  category: RuleCategory;
  regulation_reference: string;
  threshold: string;
  status: string;
  metadata: {
    regulation: string;
    section: string;
    clause?: string | null;
    description: string;
    category: RuleCategory;
    effective_date: string;
    source_url?: string | null;
  };
}

export interface RuleListResponse {
  rules: RuleDetail[];
  total_count: number;
  ruleset_version: string;
  categories: Record<RuleCategory, number>;
}

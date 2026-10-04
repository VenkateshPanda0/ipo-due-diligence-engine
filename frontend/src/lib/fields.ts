/** Field catalogue for the facts table (mirrors backend app/models/field_paths.py). */
import type { FieldKind } from "./forms";

export const FISCAL_FIELDS: { key: string; label: string; critical?: boolean }[] = [
  { key: "net_tangible_assets", label: "Net tangible assets", critical: true },
  { key: "monetary_assets", label: "Monetary assets", critical: true },
  { key: "operating_profit", label: "Operating profit", critical: true },
  { key: "net_worth", label: "Net worth", critical: true },
  { key: "revenue", label: "Revenue from operations" },
  { key: "pat", label: "Profit after tax" },
  { key: "total_assets", label: "Total assets" },
  { key: "total_liabilities", label: "Total liabilities" },
  { key: "paid_up_capital", label: "Paid-up capital" },
  { key: "reserves_and_surplus", label: "Reserves / other equity" },
  { key: "ebitda", label: "EBITDA" },
];

export const SCALAR_GROUPS: { title: string; fields: { path: string; label: string; kind: FieldKind; unit?: string }[] }[] = [
  {
    title: "Issue structure",
    fields: [
      { path: "issue_details.issue_size", label: "Issue size", kind: "decimal", unit: "INR_CRORE" },
      { path: "issue_details.post_issue_paid_up_capital", label: "Post-issue paid-up capital", kind: "decimal", unit: "INR_CRORE" },
      { path: "issue_details.expected_market_cap", label: "Post-issue capital at offer price", kind: "decimal", unit: "INR_CRORE" },
      { path: "issue_details.public_offer_percentage", label: "Public offer (% of post-issue capital)", kind: "decimal", unit: "PERCENT" },
      { path: "issue_details.qib_net_offer_allocation", label: "QIB allocation (% of net offer)", kind: "decimal", unit: "PERCENT" },
    ],
  },
  {
    title: "Promoters",
    fields: [
      { path: "promoter.post_issue_holding", label: "Post-issue promoter holding", kind: "decimal", unit: "PERCENT" },
      { path: "promoter.holding_percentage", label: "Pre-issue promoter holding", kind: "decimal", unit: "PERCENT" },
      { path: "promoter.eligible_non_promoter_contribution", label: "Eligible non-promoter contribution (Reg 14 proviso)", kind: "decimal", unit: "PERCENT" },
      { path: "promoter.lock_in_months", label: "Lock-in of minimum contribution", kind: "int", unit: "MONTHS" },
    ],
  },
  {
    title: "Eligibility declarations (ICDR Reg 5, 6(1)(d))",
    fields: [
      { path: "declarations.debarred_by_sebi", label: "Issuer / promoter / director debarred by SEBI", kind: "bool" },
      { path: "declarations.promoter_or_director_of_debarred_company", label: "Promoter/director of a debarred company", kind: "bool" },
      { path: "declarations.wilful_defaulter_or_fraudulent_borrower", label: "Wilful defaulter or fraudulent borrower", kind: "bool" },
      { path: "declarations.fugitive_economic_offender", label: "Fugitive economic offender", kind: "bool" },
      { path: "declarations.outstanding_convertibles_not_exempt", label: "Non-exempt outstanding convertibles", kind: "bool" },
      { path: "declarations.name_changed_within_last_year", label: "Name changed within the last year", kind: "bool" },
      { path: "declarations.revenue_pct_from_new_name_activity", label: "Revenue from new-name activity", kind: "decimal", unit: "PERCENT" },
    ],
  },
  {
    title: "Governance",
    fields: [
      { path: "governance.total_directors", label: "Total directors", kind: "int" },
      { path: "governance.independent_directors", label: "Independent directors", kind: "int" },
      { path: "governance.is_chair_executive", label: "Chairperson is executive", kind: "bool" },
      { path: "governance.is_chair_promoter", label: "Chairperson is a promoter / related", kind: "bool" },
      { path: "governance.audit_committee.total_members", label: "Audit committee members", kind: "int" },
      { path: "governance.audit_committee.independent_members", label: "Independent audit committee members", kind: "int" },
      { path: "governance.audit_committee.chair_is_independent", label: "Audit committee chair independent", kind: "bool" },
    ],
  },
  {
    title: "Diligence indicators",
    fields: [
      { path: "rpt.total_rpt_value", label: "Related party transactions (total)", kind: "decimal", unit: "INR_CRORE" },
      { path: "rpt.arm_length_certified", label: "RPTs certified at arm's length", kind: "bool" },
      { path: "auditor.has_qualifications", label: "Auditor qualifications", kind: "bool" },
      { path: "auditor.has_modified_opinion", label: "Modified audit opinion", kind: "bool" },
      { path: "litigation.total_exposure", label: "Litigation exposure", kind: "decimal", unit: "INR_CRORE" },
      { path: "litigation.has_criminal_cases", label: "Pending criminal cases", kind: "bool" },
    ],
  },
];

export function getPath(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((node, key) => (node && typeof node === "object" ? (node as Record<string, unknown>)[key] : undefined), obj);
}

export function kindForPath(path: string): FieldKind {
  if (path.startsWith("financials.")) return "decimal";
  for (const g of SCALAR_GROUPS) for (const f of g.fields) if (f.path === path) return f.kind;
  return "decimal";
}

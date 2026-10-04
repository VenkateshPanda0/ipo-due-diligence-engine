/** Client-side form validation (mirrors, never replaces, backend validation). */

export const ROUTES = [
  {
    id: "mainboard_reg6_1",
    title: "Main board — Regulation 6(1)",
    body: "Net tangible assets, operating profit and net worth track-record tests (ICDR Reg 6(1)(a)–(d)).",
  },
  {
    id: "mainboard_reg6_2",
    title: "Main board — Regulation 6(2)",
    body: "For issuers not meeting Reg 6(1): book-built issue with at least 75% of the net offer to QIBs.",
  },
  {
    id: "sme_chapter_ix",
    title: "SME platform — Chapter IX",
    body: "Not supported by the current ruleset. Cases on this route are reported as unsupported scope.",
  },
] as const;

export function validateCaseForm(name: string): string | null {
  const trimmed = name.trim();
  if (!trimmed) return "Company name is required.";
  if (trimmed.length > 300) return "Company name must be at most 300 characters.";
  return null;
}

export type FieldKind = "decimal" | "int" | "bool";

/** Validate a manually entered value for a field kind. Returns an error message or null. */
export function validateFieldValue(kind: FieldKind, raw: string): string | null {
  const v = raw.trim();
  if (!v) return "Enter a value.";
  if (kind === "bool") return ["true", "false", "yes", "no"].includes(v.toLowerCase()) ? null : "Choose yes or no.";
  if (kind === "int") return /^-?\d+$/.test(v) ? null : "Enter a whole number.";
  return /^-?\d+(\.\d+)?$/.test(v) ? null : "Enter a number (use a dot for decimals, no commas).";
}

export function validateCorrection(action: string, value: string, reason: string, kind: FieldKind): string | null {
  if ((action === "correct" || action === "reject") && !reason.trim()) return "A reason is required.";
  if (action === "correct") return validateFieldValue(kind, value);
  return null;
}

export const ACCEPTED_UPLOAD = "application/pdf";

export function validateUpload(file: File, maxMb: number): string | null {
  if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== ACCEPTED_UPLOAD) return "Only PDF files are supported.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > maxMb * 1024 * 1024) return `The file exceeds the ${maxMb} MB limit.`;
  return null;
}

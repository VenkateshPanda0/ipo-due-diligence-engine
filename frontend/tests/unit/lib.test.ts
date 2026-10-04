import { describe, expect, it } from "vitest";
import { fieldLabel, formatValue, humanize, outcomeLabel } from "@/lib/format";
import { validateCaseForm, validateCorrection, validateFieldValue, validateUpload } from "@/lib/forms";
import { Report } from "@/lib/schemas";

describe("form validation", () => {
  it("requires a company name", () => {
    expect(validateCaseForm("   ")).toMatch(/required/);
    expect(validateCaseForm("Acme")).toBeNull();
    expect(validateCaseForm("x".repeat(301))).toMatch(/300/);
  });
  it("validates field values by kind", () => {
    expect(validateFieldValue("decimal", "12.5")).toBeNull();
    expect(validateFieldValue("decimal", "1,234")).toMatch(/no commas/);
    expect(validateFieldValue("int", "3.5")).toMatch(/whole/);
    expect(validateFieldValue("bool", "maybe")).toMatch(/yes or no/);
    expect(validateFieldValue("bool", "No")).toBeNull();
  });
  it("requires a reason to correct or reject", () => {
    expect(validateCorrection("correct", "10", "", "decimal")).toMatch(/reason/);
    expect(validateCorrection("reject", "", "dup", "decimal")).toBeNull();
    expect(validateCorrection("confirm", "", "", "decimal")).toBeNull();
  });
  it("validates uploads before sending", () => {
    expect(validateUpload(new File(["x"], "a.txt", { type: "text/plain" }), 50)).toMatch(/PDF/);
    expect(validateUpload(new File([], "a.pdf", { type: "application/pdf" }), 50)).toMatch(/empty/);
    expect(validateUpload(new File(["x".repeat(2 * 1024 * 1024)], "a.pdf"), 1)).toMatch(/1 MB/);
    expect(validateUpload(new File(["%PDF"], "a.pdf"), 1)).toBeNull();
  });
});

describe("formatting", () => {
  it("formats values without changing them", () => {
    expect(formatValue("123.4567", "INR_CRORE")).toBe("₹123.4567 Cr");
    expect(formatValue(false)).toBe("No");
    expect(formatValue(null)).toBe("—");
    expect(formatValue("25", "PERCENT")).toBe("25%");
  });
  it("labels field paths", () => {
    expect(fieldLabel("financials.fiscal_years[FY2024].net_worth")).toBe("Net worth · FY2024");
    expect(humanize("awaiting_review")).toBe("Awaiting review");
  });
  it("never says 'eligible' for the best outcome", () => {
    expect(outcomeLabel.no_failure_identified).not.toMatch(/eligible/i);
  });
});

describe("runtime contract validation", () => {
  it("rejects a malformed report payload", () => {
    expect(Report.safeParse({ report_id: "x", status: "eligible" }).success).toBe(false);
  });
});

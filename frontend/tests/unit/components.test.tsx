import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { RuleResultItem } from "@/components/report/RuleResults";
import { Badge, EmptyState, ErrorState, Modal, Tabs } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { RuleResult } from "@/lib/schemas";

const wrap = (ui: ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

const rule = RuleResult.parse({
  rule_id: "NTA_3CR",
  verdict: "fail",
  category: "mandatory",
  regulation_reference: "SEBI (ICDR) Regulations, 2018, Regulation 6(1)(a)",
  description: "NTA",
  required_value: "≥ ₹3.00 Cr NTA in each of the 3 preceding full years",
  actual_value: "FY2022: ₹2.00 Cr",
  gap: "₹1.00 Cr below threshold in FY2022",
  explanation: "Net tangible assets were below ₹3.00 Cr in FY2022.",
  rule_name: "Net tangible assets of at least ₹3 crore",
  calculation: ["FY2022: ₹2.00 Cr ≥ ₹3.00 Cr → False"],
  evidence: [
    { field_path: "financials.FY2022.net_tangible_assets", value: "2", unit: "INR_CRORE", kind: "extracted", source_document: "drhp.pdf", page_number: 12, original_text: "200.00", original_unit: "INR_LAKH" },
    { field_path: "x.ratio", value: "50", kind: "calculated" },
  ],
  missing_inputs: [],
  remediation: ["Consider Reg 6(2)."],
  verification_status: "primary_text_checked",
  legal_category: "statutory_eligibility",
});

describe("RuleResultItem", () => {
  it("explains a failure with calculation, evidence and remediation", () => {
    wrap(<RuleResultItem r={rule} defaultOpen resolveDoc={() => "doc-1"} />);
    expect(screen.getByText("Fail")).toBeInTheDocument();
    expect(screen.getByText(/₹1.00 Cr below threshold/)).toBeInTheDocument();
    expect(screen.getByText("FY2022: ₹2.00 Cr ≥ ₹3.00 Cr → False")).toBeInTheDocument();
    expect(screen.getByText("200.00")).toBeInTheDocument();
    expect(screen.getByText("Extracted from document")).toBeInTheDocument();
    expect(screen.getByText("Calculated by rule")).toBeInTheDocument();
    expect(screen.getByText(/not a guarantee of eligibility/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View" })).toBeInTheDocument();
  });

  it("renders extracted text as text, not HTML", () => {
    const evil = RuleResult.parse({ ...rule, explanation: '<img src=x onerror="alert(1)">' });
    const { container } = wrap(<RuleResultItem r={evil} defaultOpen />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument();
  });
});

describe("UI primitives", () => {
  it("shows API error code context and retry", () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError(404, "NOT_FOUND", "case 'x' not found.", "req-1")} onRetry={retry} />);
    expect(screen.getByText(/case 'x' not found/)).toBeInTheDocument();
    expect(screen.getByText("req-1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalled();
  });
  it("tells unauthenticated users what to do", () => {
    render(<ErrorState error={new ApiError(401, "UNAUTHORIZED", "Invalid or missing API key.")} />);
    expect(screen.getByText("Authentication required")).toBeInTheDocument();
  });
  it("tabs expose aria-selected", () => {
    const change = vi.fn();
    render(<Tabs value="a" onChange={change} tabs={[{ id: "a", label: "A" }, { id: "b", label: "B", count: 2 }]} />);
    expect(screen.getByRole("tab", { name: "A" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: /B/ }));
    expect(change).toHaveBeenCalledWith("b");
  });
  it("modal closes on Escape and is labelled", () => {
    const close = vi.fn();
    render(<Modal title="Page 2" onClose={close}>body</Modal>);
    expect(screen.getByRole("dialog", { name: "Page 2" })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(close).toHaveBeenCalled();
  });
  it("empty state and badge render", () => {
    render(<><EmptyState title="Nothing here">hint</EmptyState><Badge tone="negative">Fail</Badge></>);
    expect(screen.getByRole("heading", { name: "Nothing here" })).toBeInTheDocument();
    expect(screen.getByText("Fail")).toHaveClass("tone-negative");
  });
});

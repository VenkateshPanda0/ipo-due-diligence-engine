/**
 * Centralised API client. The backend is the only source of screening results;
 * this module never computes regulatory outcomes.
 */
import { z } from "zod";
import { getApiKey } from "./auth";
import {
  Case,
  CaseList,
  DocumentInfo,
  Report,
  ReviewItem,
  type TCase,
  type TDocument,
  type TReport,
  type TReviewItem,
} from "./schemas";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId?: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function toError(response: Response): Promise<ApiError> {
  let code = `HTTP_${response.status}`;
  let message = `Request failed (${response.status}).`;
  let requestId = response.headers.get("X-Request-ID") ?? undefined;
  let details: unknown;
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; request_id?: string; details?: unknown };
    };
    if (body.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      requestId = body.error.request_id ?? requestId;
      details = body.error.details;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(response.status, code, message, requestId, details);
}

function headers(extra?: HeadersInit): HeadersInit {
  const key = getApiKey();
  return { ...(key ? { Authorization: `Bearer ${key}` } : {}), ...(extra ?? {}) };
}

async function raw(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers: headers(init?.headers) });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", `Cannot reach the API at ${API_BASE_URL}. Is the backend running?`);
  }
  if (!response.ok) throw await toError(response);
  return response;
}

async function json<T>(path: string, schema: z.ZodType<T, z.ZodTypeDef, unknown> | null, init?: RequestInit): Promise<T> {
  const response = await raw(path, {
    ...init,
    headers: init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
  });
  const data: unknown = await response.json();
  if (!schema) return data as T;
  const parsed = schema.safeParse(data);
  if (!parsed.success) {
    throw new ApiError(0, "CONTRACT_MISMATCH", `Unexpected response from ${path}: ${parsed.error.issues[0]?.message ?? "invalid"}`);
  }
  return parsed.data;
}

const post = (body?: unknown): RequestInit => ({ method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export type Dashboard = {
  cases_total: number;
  cases_by_status: Record<string, number>;
  cases_awaiting_review: number;
  open_review_items: number;
  reports_total: number;
  reports_by_outcome: Record<string, number>;
  documents_failed: number;
  documents_processing: number;
  ruleset_version: string;
  recent_activity: { ts: string; actor: string; action: string; entity_type: string; entity_id: string; case_id: string | null }[];
};

export type Extraction = {
  document_id: string;
  run: null | {
    id: string;
    pipeline_version: string;
    status: string;
    summary: { metrics?: Record<string, number>; warnings?: string[]; doc_type?: string; suggestions?: Record<string, { value: unknown; page: number; snippet: string }> };
    pages: { page: number; kind: string; method: string; chars: number; ocr_mean_conf: number | null; readable: boolean; warnings: string[]; rotation: number }[];
    environment: Record<string, unknown>;
    error_message: string | null;
  };
  fields: { field_path: string; status: string; selected: Record<string, unknown> | null; candidates: Record<string, unknown>[]; reason: string | null; score: number | null }[];
};

export type RuleSpec = {
  rule_id: string;
  rule_version: string;
  name: string;
  category: "mandatory" | "advisory";
  legal_category: string;
  routes: string[];
  instrument: string;
  provision: string;
  source_url: string | null;
  effective_from: string | null;
  effective_to: string | null;
  applicability: string;
  required_inputs: string[];
  decision_procedure: string;
  parameters: Record<string, string>;
  evidence_requirements: string;
  limitations: string[];
  verification_status: string;
  required_value: string;
  sources: { source_id: string; title: string; kind: string; url: string | null; document_sha256: string | null; accessed_on: string | null; notes: string }[];
};

export type Capabilities = {
  api_version: string;
  pipeline_version: string;
  ruleset: { version: string; status: string; effective_from: string; supported_routes: string[]; unsupported_routes: string[]; legal_review_confirmed: boolean };
  regulatory_validation_confirmed: boolean;
  supported_document_types: string[];
  ocr: { enabled: boolean; available: boolean; tesseract_version: string | null; max_ocr_pages: number; dpi: number };
  limits: Record<string, number>;
  auth: { enabled: boolean; mode: string };
  retention: { retain_documents: boolean; retention_days: number };
  database: { backend: string; reachable: boolean };
  external_services: string[];
};

export const api = {
  health: () => json<{ status: string; version: string; database: boolean; ruleset_version: string }>("/api/v1/system/health", null),
  capabilities: () => json<Capabilities>("/api/v1/system/capabilities", null),
  me: () => json<{ user_id: string; role: string; authenticated: boolean }>("/api/v1/me", null),
  dashboard: () => json<Dashboard>("/api/v1/dashboard", null),

  listCases: (params: { q?: string; status?: string } = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
    return json("/api/v1/cases" + (qs ? `?${qs}` : ""), CaseList);
  },
  createCase: (body: { company_name: string; listing_route: string; notes?: string }): Promise<TCase> =>
    json("/api/v1/cases", Case, post(body)),
  getCase: (id: string): Promise<TCase> => json(`/api/v1/cases/${id}`, Case),
  updateCase: (id: string, body: Record<string, unknown>): Promise<TCase> =>
    json(`/api/v1/cases/${id}`, Case, { method: "PATCH", body: JSON.stringify(body) }),
  caseData: (id: string) =>
    json<{ version: number; source: string; reason: string | null; created_by: string; created_at: string; payload: Record<string, unknown> }>(`/api/v1/cases/${id}/data`, null),
  caseVersions: (id: string) =>
    json<{ version: number; source: string; reason: string | null; created_by: string; created_at: string }[]>(`/api/v1/cases/${id}/data/versions`, null),
  setFields: (id: string, updates: { field_path: string; value: unknown; note?: string; period_end?: string }[]) =>
    json(`/api/v1/cases/${id}/fields`, null, { method: "PATCH", body: JSON.stringify({ updates }) }),
  replaceData: (id: string, payload: Record<string, unknown>, reason?: string) =>
    json(`/api/v1/cases/${id}/data`, null, { method: "PUT", body: JSON.stringify({ payload, reason }) }),
  caseHistory: (id: string) =>
    json<{ ts: string; actor: string; action: string; entity_type: string; entity_id: string; details: Record<string, unknown> }[]>(`/api/v1/cases/${id}/history`, null),

  caseDocuments: (id: string): Promise<TDocument[]> => json(`/api/v1/cases/${id}/documents`, z.array(DocumentInfo)),
  uploadDocument: (caseId: string, file: File): Promise<TDocument> => {
    const data = new FormData();
    data.append("file", file);
    return json(`/api/v1/cases/${caseId}/documents`, DocumentInfo, { method: "POST", body: data });
  },
  getDocument: (id: string): Promise<TDocument> => json(`/api/v1/documents/${id}`, DocumentInfo),
  retryDocument: (id: string): Promise<TDocument> => json(`/api/v1/documents/${id}/retry`, DocumentInfo, post()),
  deleteDocumentContent: (id: string): Promise<TDocument> =>
    json(`/api/v1/documents/${id}/content`, DocumentInfo, { method: "DELETE" }),
  extraction: (id: string) => json<Extraction>(`/api/v1/documents/${id}/extraction`, null),
  pageImage: async (id: string, page: number): Promise<string> => {
    const response = await raw(`/api/v1/documents/${id}/pages/${page}/image`);
    return URL.createObjectURL(await response.blob());
  },

  reviewItems: (params: { case_id?: string; status?: string } = {}): Promise<TReviewItem[]> => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][]).toString();
    return json(`/api/v1/review-items${qs ? `?${qs}` : ""}`, z.array(ReviewItem));
  },
  resolveItem: (id: string, body: { action: string; value?: unknown; reason?: string }): Promise<TReviewItem> =>
    json(`/api/v1/review-items/${id}/resolve`, ReviewItem, post(body)),

  screenCase: (id: string): Promise<TReport> => json(`/api/v1/cases/${id}/screenings`, Report, post()),
  caseScreenings: (id: string) =>
    json<{ report_id: string; data_version: number | null; ruleset_version: string; outcome: string | null; legacy_status: string; created_by: string; created_at: string }[]>(`/api/v1/cases/${id}/screenings`, null),
  listReports: () =>
    json<{ report_id: string; case_id: string | null; company_name: string; ruleset_version: string; outcome: string | null; legacy_status: string; created_at: string }[]>("/api/v1/reports", null),
  getReport: (id: string): Promise<TReport> => json(`/api/v1/reports/${id}`, Report),
  exportReport: async (id: string, format: "html" | "json" | "text"): Promise<Blob> =>
    (await raw(`/api/v1/reports/${id}/export?format=${format}`)).blob(),
  signOff: (id: string) => json<{ review: null | Record<string, unknown>; history: Record<string, unknown>[] }>(`/api/v1/reports/${id}/sign-off`, null),
  submitSignOff: (id: string, body: { reviewer_name: string; final_decision: string; rationale: string; conditions: string[] }) =>
    json<{ review: Record<string, unknown>; history: Record<string, unknown>[] }>(`/api/v1/reports/${id}/sign-off`, null, post(body)),

  rules: () => json<{ ruleset_version: string; rules: RuleSpec[] }>("/api/v1/rules", null),
  rulesets: () =>
    json<{ version: string; status: string; effective_from: string; effective_to: string | null; description: string; change_summary: string[]; rule_count: number; legal_review: { confirmed: boolean } }[]>("/api/v1/rulesets", null),
};

import type {
  HumanReviewDecisionRequest,
  HumanReviewResponse,
  RuleDetail,
  RuleListResponse,
  ScreeningResponse,
} from "../types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function errorMessage(response: Response): Promise<string> {
  const body = await response.text();
  if (!body) return `Request failed with ${response.status}`;
  try {
    const parsed = JSON.parse(body) as { error?: { code?: string; message?: string } };
    if (parsed.error?.message) {
      return parsed.error.code ? `${parsed.error.code}: ${parsed.error.message}` : parsed.error.message;
    }
  } catch {
    return body;
  }
  return body;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return response.json() as Promise<T>;
}

export const ipoApi = {
  screenJSON(companyData: unknown): Promise<ScreeningResponse> {
    return request<ScreeningResponse>("/screen/json", {
      method: "POST",
      body: JSON.stringify(companyData),
    });
  },

  async screenPDF(file: File): Promise<ScreeningResponse> {
    const data = new FormData();
    data.append("file", file);
    const response = await fetch(`${API_BASE_URL}/screen/pdf`, {
      method: "POST",
      body: data,
    });
    if (!response.ok) {
      throw new Error(await errorMessage(response));
    }
    return response.json() as Promise<ScreeningResponse>;
  },

  getReport(reportId: string): Promise<ScreeningResponse> {
    return request<ScreeningResponse>(`/reports/${reportId}`);
  },

  openReview(reportId: string): Promise<HumanReviewResponse> {
    return request<HumanReviewResponse>(`/reviews/reports/${reportId}`, {
      method: "POST",
    });
  },

  completeReview(reviewId: string, decision: HumanReviewDecisionRequest): Promise<HumanReviewResponse> {
    return request<HumanReviewResponse>(`/reviews/${reviewId}/decision`, {
      method: "POST",
      body: JSON.stringify(decision),
    });
  },

  getRules(category?: "mandatory" | "advisory"): Promise<RuleListResponse> {
    const query = category ? `?category=${category}` : "";
    return request<RuleListResponse>(`/rules${query}`);
  },

  getRuleDetail(ruleId: string): Promise<RuleDetail> {
    return request<RuleDetail>(`/rules/${ruleId}`);
  },
};

import type { AnalyzeResponse, ChatResponse, Quota } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError("Cannot reach the FinGuard API. Is the backend running?", 0);
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) detail = "The request was rejected by input validation.";
    } catch {
      /* non-JSON error body: keep the generic message */
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export interface StatementInput {
  csvText: string | null;
  useSample: boolean;
}

export function analyzeStatement({ csvText, useSample }: StatementInput) {
  return request<AnalyzeResponse>("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ csv_text: useSample ? null : csvText, use_sample: useSample }),
  });
}

export function askAnalyst(prompt: string, { csvText, useSample }: StatementInput) {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ prompt, csv_text: useSample ? null : csvText, use_sample: useSample }),
  });
}

export function fetchQuota() {
  return request<Quota>("/api/quota");
}

export function fetchHealth() {
  return request<{ status: string; model: string; live_ai_enabled: boolean }>("/api/health");
}

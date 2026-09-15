import axios, { AxiosError } from "axios";
import type { ProblemDetail } from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "shadow_ledger_token";

export const api = axios.create({ baseURL: API_BASE, timeout: 15000 });

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // private-browsing / blocked storage — fall back to logged-out
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable — session just won't persist across reload */
  }
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Normalized app-facing error — every caller can rely on this shape
 * regardless of whether the backend returned a structured problem+json body,
 * a network failure, or a timeout. */
export class ApiError extends Error {
  status: number | null;
  errorType: string | null;
  correlationId: string | null;
  fieldErrors: Array<{ field: string; message: string }>;
  isNetworkError: boolean;

  constructor(opts: {
    message: string;
    status?: number | null;
    errorType?: string | null;
    correlationId?: string | null;
    fieldErrors?: Array<{ field: string; message: string }>;
    isNetworkError?: boolean;
  }) {
    super(opts.message);
    this.status = opts.status ?? null;
    this.errorType = opts.errorType ?? null;
    this.correlationId = opts.correlationId ?? null;
    this.fieldErrors = opts.fieldErrors ?? [];
    this.isNetworkError = opts.isNetworkError ?? false;
  }
}

export function toApiError(err: unknown): ApiError {
  if (axios.isAxiosError(err)) {
    const ax = err as AxiosError<ProblemDetail>;
    if (!ax.response) {
      return new ApiError({
        message: ax.code === "ECONNABORTED"
          ? "The request timed out. Check your connection and try again."
          : "Could not reach the server. Check your connection and try again.",
        isNetworkError: true,
      });
    }
    const body = ax.response.data;
    const fieldErrors = (body?.errors ?? []).map((e) => ({
      field: e.loc.slice(1).join("."),
      message: e.msg,
    }));
    return new ApiError({
      message: body?.detail ?? ax.message,
      status: ax.response.status,
      errorType: body?.type?.split("/").pop() ?? null,
      correlationId: body?.correlation_id ?? null,
      fieldErrors,
    });
  }
  return new ApiError({ message: err instanceof Error ? err.message : "An unexpected error occurred." });
}

/** RFC 4122 v4 — good enough for a client-generated idempotency key (never
 * used for anything security-sensitive, just request deduplication). */
export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

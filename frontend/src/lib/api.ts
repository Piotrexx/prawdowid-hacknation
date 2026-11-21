import type {
  AdminCheckItem,
  AdminMetrics,
  CheckRequest,
  CheckResponse,
  HealthResponse,
} from "./types";

interface SessionDeleteResponse {
  deleted: number;
}

const API_ROOT = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export const API_BASE = `${API_ROOT}/api/v1`;

export type ApiErrorKind =
  | "network"
  | "timeout"
  | "rate_limit"
  | "validation"
  | "not_found"
  | "unauthorized"
  | "http";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly detail?: string;
  readonly retryAfterSeconds?: number;

  constructor(
    kind: ApiErrorKind,
    options: { status?: number; detail?: string; retryAfterSeconds?: number } = {},
  ) {
    super(options.detail ?? kind);
    this.name = "ApiError";
    this.kind = kind;
    this.status = options.status;
    this.detail = options.detail;
    this.retryAfterSeconds = options.retryAfterSeconds;
  }
}

const DEFAULT_TIMEOUT_MS = 20_000;
const CHECK_TIMEOUT_MS = 120_000;

interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) return undefined;
  const seconds = Number(value);
  if (Number.isFinite(seconds)) return Math.max(0, Math.ceil(seconds));
  const date = Date.parse(value);
  if (Number.isNaN(date)) return undefined;
  return Math.max(0, Math.ceil((date - Date.now()) / 1000));
}

async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) return detail;
    }
  } catch {
    // Non-JSON error bodies carry nothing we can show.
  }
  return undefined;
}

async function toApiError(response: Response): Promise<ApiError> {
  const detail = await readDetail(response);
  const status = response.status;
  if (status === 429) {
    return new ApiError("rate_limit", {
      status,
      detail,
      retryAfterSeconds: parseRetryAfter(response.headers.get("Retry-After")),
    });
  }
  if (status === 422 || status === 400 || status === 413 || status === 415) {
    return new ApiError("validation", { status, detail });
  }
  if (status === 404) return new ApiError("not_found", { status, detail });
  if (status === 401 || status === 403) {
    return new ApiError("unauthorized", { status, detail });
  }
  return new ApiError("http", { status, detail });
}

async function send(path: string, options: RequestOptions = {}): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal, ...init } = options;
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", onAbort);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
    });
    if (!response.ok) throw await toApiError(response);
    return response;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (signal?.aborted) throw error;
    throw new ApiError(timedOut ? "timeout" : "network");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

async function getJson<T>(path: string, options?: RequestOptions): Promise<T> {
  const response = await send(path, options);
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("http", { status: response.status });
  }
}

export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson("/health", { signal });
}

export function createCheck(
  body: CheckRequest,
  signal?: AbortSignal,
): Promise<CheckResponse> {
  return getJson("/checks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    timeoutMs: CHECK_TIMEOUT_MS,
    signal,
  });
}

export function getCheck(id: string, signal?: AbortSignal): Promise<CheckResponse> {
  return getJson(`/checks/${encodeURIComponent(id)}`, { signal });
}

export function deleteSession(sessionId: string): Promise<SessionDeleteResponse> {
  return getJson(`/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

function adminHeaders(token: string): HeadersInit {
  return { "X-Admin-Token": token };
}

export function getMetrics(token: string, signal?: AbortSignal): Promise<AdminMetrics> {
  return getJson("/admin/metrics", { headers: adminHeaders(token), signal });
}

export function getRecentChecks(
  token: string,
  signal?: AbortSignal,
  limit = 50,
): Promise<AdminCheckItem[]> {
  return getJson(`/admin/checks?limit=${limit}`, {
    headers: adminHeaders(token),
    signal,
  });
}

export async function downloadExport(
  token: string,
  format: "csv" | "json",
): Promise<{ blob: Blob; filename: string | null }> {
  const response = await send(`/admin/export?format=${format}`, {
    headers: adminHeaders(token),
    timeoutMs: 60_000,
  });
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="?([^";]+)"?/i.exec(disposition)?.[1] ?? null;
  return { blob: await response.blob(), filename };
}
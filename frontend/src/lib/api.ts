import type {
  ArchiveOut,
  CaseOut,
  CaseStatus,
  CaseUpdate,
  CheckListItem,
  CheckRequest,
  CheckResponse,
  Comment,
  ConsentResponse,
  HealthResponse,
  LlmProvider,
  LlmSettings,
  LlmSettingsUpdate,
  MetricsResponse,
  Moderator,
  ModeratorCreated,
  ModeratorLoginResponse,
  ModeratorPasswordReset,
  Profile,
  ProfileUpdate,
  PushPublicKey,
  SecurityEventOut,
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
const CHECK_TIMEOUT_MS = 180_000;

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
      // Numer sesji i zgoda jadą w ciasteczkach, więc backend musi je dostać.
      // Wymaga allow_credentials=True w CORS po stronie backendu.
      credentials: "include",
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

// --- Public API ---

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson("/health", { signal });
}

export async function createCheck(
  body: CheckRequest,
  signal?: AbortSignal,
): Promise<CheckResponse> {
  if (!body.url && !body.text) {
    throw new ApiError("validation", {
      detail: "Podaj link lub tekst do sprawdzenia.",
    });
  }
  const payload: Record<string, unknown> = { session_id: body.session_id };
  if (body.url) payload.url = body.url;
  if (body.text) payload.text = body.text;
  return getJson<CheckResponse>("/checks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    timeoutMs: CHECK_TIMEOUT_MS,
    signal,
  });
}

/** XHR-based multipart upload that fires `onUploadProgress(0..100)` during the upload phase. */
function xhrUpload<T>(
  path: string,
  form: FormData,
  onUploadProgress: (pct: number) => void,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`, true);
    xhr.withCredentials = true;
    xhr.timeout = CHECK_TIMEOUT_MS;

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onUploadProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(new ApiError("http", { status: xhr.status }));
        }
      } else {
        let detail: string | undefined;
        try {
          const body: unknown = JSON.parse(xhr.responseText);
          if (body && typeof body === "object" && "detail" in body) {
            const d = (body as { detail: unknown }).detail;
            if (typeof d === "string" && d.trim()) detail = d;
          }
        } catch { /* ignore */ }
        const status = xhr.status;
        if (status === 429) reject(new ApiError("rate_limit", { status, detail }));
        else if (status === 422 || status === 400 || status === 413 || status === 415) reject(new ApiError("validation", { status, detail }));
        else if (status === 404) reject(new ApiError("not_found", { status, detail }));
        else if (status === 401 || status === 403) reject(new ApiError("unauthorized", { status, detail }));
        else reject(new ApiError("http", { status, detail }));
      }
    };

    xhr.onerror = () => reject(new ApiError("network"));
    xhr.ontimeout = () => reject(new ApiError("timeout"));

    const onAbort = () => xhr.abort();
    signal?.addEventListener("abort", onAbort);
    xhr.onabort = () => {
      signal?.removeEventListener("abort", onAbort);
      reject(new DOMException("Aborted", "AbortError"));
    };

    xhr.send(form);
  });
}

export async function createImageCheck(
  file: File,
  sessionId?: string,
  signal?: AbortSignal,
  onUploadProgress?: (pct: number) => void,
): Promise<CheckResponse> {
  const body = new FormData();
  body.append("file", file);
  if (sessionId) body.append("session_id", sessionId);
  if (onUploadProgress) {
    return xhrUpload<CheckResponse>("/checks/image", body, onUploadProgress, signal);
  }
  // No Content-Type header: the browser sets the multipart boundary itself.
  return getJson<CheckResponse>("/checks/image", {
    method: "POST",
    body,
    timeoutMs: CHECK_TIMEOUT_MS,
    signal,
  });
}

export async function createAudioCheck(
  file: File,
  sessionId?: string,
  signal?: AbortSignal,
  onUploadProgress?: (pct: number) => void,
): Promise<CheckResponse> {
  const body = new FormData();
  body.append("file", file);
  if (sessionId) body.append("session_id", sessionId);
  if (onUploadProgress) {
    return xhrUpload<CheckResponse>("/checks/audio", body, onUploadProgress, signal);
  }
  return getJson<CheckResponse>("/checks/audio", {
    method: "POST",
    body,
    timeoutMs: CHECK_TIMEOUT_MS,
    signal,
  });
}

export function getCheck(id: string, signal?: AbortSignal): Promise<CheckResponse> {
  return getJson<CheckResponse>(`/checks/${encodeURIComponent(id)}`, { signal });
}

export function archiveCheck(
  checkId: string,
  sessionId?: string,
): Promise<ArchiveOut> {
  return getJson<ArchiveOut>("/archive", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ check_id: checkId, session_id: sessionId }),
  });
}

export function getArchive(id: string): Promise<ArchiveOut> {
  return getJson<ArchiveOut>(`/archive/${encodeURIComponent(id)}`);
}

export function deleteArchive(id: string): Promise<{ deleted: boolean }> {
  return getJson(`/archive/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function deleteSession(sessionId: string): Promise<SessionDeleteResponse> {
  return getJson(`/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}

export function recordConsent(
  sessionId: string,
  policyVersion: string,
  accepted = true,
): Promise<ConsentResponse> {
  return getJson<ConsentResponse>("/consent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      policy_version: policyVersion,
      accepted,
    }),
  });
}

export async function hasConsent(
  sessionId: string,
  policyVersion: string,
  signal?: AbortSignal,
): Promise<boolean> {
  try {
    await getJson<ConsentResponse>(
      `/consent/${encodeURIComponent(sessionId)}?policy_version=${encodeURIComponent(policyVersion)}`,
      { signal },
    );
    return true;
  } catch (error) {
    // 404 simply means this session has not accepted this policy version yet.
    if (error instanceof ApiError && error.kind === "not_found") return false;
    throw error;
  }
}

function adminHeaders(token: string): HeadersInit {
  // `X-Admin-Token` zachowuje zgodność z tokenem technicznym; `Authorization`
  // obsługuje sesję konta moderatora. Wysłanie obu pozwala używać obu trybów.
  return { Authorization: `Bearer ${token}`, "X-Admin-Token": token };
}

// Token sesji moderatora. Wysyłamy go w nagłówku Authorization; przeglądarka
// dostaje też ciasteczko HttpOnly, więc panel działa również po odświeżeniu.
function authHeaders(token: string): HeadersInit {
  return adminHeaders(token);
}

export function loginModerator(
  email: string,
  password: string,
): Promise<ModeratorLoginResponse> {
  return getJson<ModeratorLoginResponse>("/admin/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function logoutModerator(token: string): Promise<{ logged_out: boolean }> {
  return getJson("/admin/auth/logout", { method: "POST", headers: authHeaders(token) });
}

export function getProfile(token: string, signal?: AbortSignal): Promise<Profile> {
  return getJson("/admin/auth/me", { headers: authHeaders(token), signal });
}

export function updateProfile(token: string, update: ProfileUpdate): Promise<Profile> {
  return getJson("/admin/auth/me", {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export function changePassword(
  token: string,
  currentPassword: string,
  newPassword: string,
): Promise<{ changed: boolean; logged_out: boolean }> {
  return getJson("/admin/auth/me/password", {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export function getCaseComments(
  token: string,
  caseId: number,
  signal?: AbortSignal,
): Promise<Comment[]> {
  return getJson(`/admin/cases/${caseId}/comments`, {
    headers: authHeaders(token),
    signal,
  });
}

export function addCaseComment(
  token: string,
  caseId: number,
  body: string,
): Promise<Comment> {
  return getJson(`/admin/cases/${caseId}/comments`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
}

export function getArticleComments(
  token: string,
  articleId: number,
  signal?: AbortSignal,
): Promise<Comment[]> {
  return getJson(`/admin/articles/${articleId}/comments`, {
    headers: authHeaders(token),
    signal,
  });
}

export function addArticleComment(
  token: string,
  articleId: number,
  body: string,
): Promise<Comment> {
  return getJson(`/admin/articles/${articleId}/comments`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ body }),
  });
}

export function deleteComment(token: string, commentId: number): Promise<{ deleted: boolean }> {
  return getJson(`/admin/comments/${commentId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export function listModerators(token: string, signal?: AbortSignal): Promise<Moderator[]> {
  return getJson("/admin/moderators", { headers: authHeaders(token), signal });
}

export function createModerator(
  token: string,
  payload: {
    email: string;
    display_name: string;
    role: "moderator" | "superuser";
    password?: string;
    must_change_password?: boolean;
  },
): Promise<ModeratorCreated> {
  return getJson("/admin/moderators", {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function updateModerator(
  token: string,
  id: number,
  payload: {
    display_name?: string;
    role?: "moderator" | "superuser";
    is_active?: boolean;
    must_change_password?: boolean;
  },
): Promise<Moderator> {
  return getJson(`/admin/moderators/${id}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function resetModeratorPassword(
  token: string,
  id: number,
): Promise<ModeratorPasswordReset> {
  return getJson(`/admin/moderators/${id}/reset-password`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function getLlmProviders(
  token: string,
  signal?: AbortSignal,
): Promise<LlmProvider[]> {
  return getJson("/admin/llm/providers", { headers: authHeaders(token), signal });
}

export function getLlmSettings(token: string, signal?: AbortSignal): Promise<LlmSettings> {
  return getJson("/admin/llm/settings", { headers: authHeaders(token), signal });
}

export function saveLlmSettings(
  token: string,
  settings: LlmSettingsUpdate,
): Promise<LlmSettings> {
  return getJson("/admin/llm/settings", {
    method: "PUT",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export function getPushPublicKey(token: string): Promise<PushPublicKey> {
  return getJson("/admin/auth/me/push-public-key", { headers: authHeaders(token) });
}

export function savePushSubscription(
  token: string,
  subscription: PushSubscriptionJSON,
): Promise<void> {
  return send("/admin/auth/me/push-subscription", {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      keys: subscription.keys,
      user_agent: navigator.userAgent,
    }),
  }).then(() => undefined);
}

export function deletePushSubscription(token: string, endpoint: string): Promise<void> {
  return send(
    `/admin/auth/me/push-subscription?endpoint=${encodeURIComponent(endpoint)}`,
    { method: "DELETE", headers: authHeaders(token) },
  ).then(() => undefined);
}

export function getMetrics(token: string, signal?: AbortSignal): Promise<MetricsResponse> {
  return getJson("/admin/metrics", { headers: adminHeaders(token), signal });
}

export function getRecentChecks(
  token: string,
  signal?: AbortSignal,
  limit = 50,
): Promise<CheckListItem[]> {
  return getJson(`/admin/checks?limit=${limit}`, {
    headers: adminHeaders(token),
    signal,
  });
}

export function getCases(
  token: string,
  status: CaseStatus | null,
  signal?: AbortSignal,
): Promise<CaseOut[]> {
  const query = status ? `?${new URLSearchParams({ status })}` : "";
  return getJson(`/admin/cases${query}`, { headers: adminHeaders(token), signal });
}

export function updateCase(
  token: string,
  id: number,
  update: CaseUpdate,
): Promise<CaseOut> {
  return getJson(`/admin/cases/${id}`, {
    method: "PATCH",
    headers: { ...adminHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export function getSecurityEvents(
  token: string,
  signal?: AbortSignal,
  limit = 50,
): Promise<SecurityEventOut[]> {
  return getJson(`/admin/events?limit=${limit}`, {
    headers: adminHeaders(token),
    signal,
  });
}

export async function downloadExport(
  token: string,
  format: "csv" | "json" | "stix",
): Promise<{ blob: Blob; filename: string | null }> {
  const path = format === "stix" ? "/admin/export/stix" : `/admin/export?format=${format}`;
  const response = await send(path, {
    headers: adminHeaders(token),
    timeoutMs: 60_000,
  });
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="?([^";]+)"?/i.exec(disposition)?.[1] ?? null;
  return { blob: await response.blob(), filename };
}

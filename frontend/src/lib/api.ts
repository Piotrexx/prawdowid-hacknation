import type {
  AdminCheckItem,
  AdminMetrics,
  CheckRequest,
  CheckResponse,
  ClaimResult,
  Evidence,
  FactCheckResult,
  HealthResponse,
  IncidentMatch,
  ModeratorCaseInfo,
  SourceRef,
  StrengthLevel,
  Verdict,
  Warning,
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

// --- Backend response → frontend shape adapter ---

/** Backend returns old verdict codes; map them to the frontend's Verdict type. */
function mapVerdict(raw: string | null | undefined): Verdict | null {
  if (!raw) return null;
  const MAP: Record<string, Verdict> = {
    fake_news: "falszywe",
    prawdziwe: "potwierdzone",
    niepewne: "brak_wystarczajacych_dowodow",
    satyna: "nie_podlega_weryfikacji",
    opinia: "nie_podlega_weryfikacji",
    // new values pass through if they already match
    falszywe: "falszywe",
    potwierdzone: "potwierdzone",
    wprowadzajace_w_blad: "wprowadzajace_w_blad",
    brak_wystarczajacych_dowodow: "brak_wystarczajacych_dowodow",
    nie_podlega_weryfikacji: "nie_podlega_weryfikacji",
  };
  return MAP[raw] ?? "brak_wystarczajacych_dowodow";
}

function confidenceToLevel(c: number | null): StrengthLevel {
  if (c === null) return "brak";
  if (c >= 0.75) return "mocna";
  if (c >= 0.5) return "umiarkowana";
  return "slaba";
}

function factCheckToEvidence(fc: FactCheckResult, index: number): Evidence {
  const r = (fc.rating ?? "").toLowerCase();
  const stance =
    r.includes("false") || r.includes("fałsz") || r.includes("nieprawda")
      ? "refutes"
      : r.includes("true") || r.includes("prawda") || r.includes("potwierdz")
        ? "supports"
        : "context";
  return {
    id: `fc-${index}`,
    stance,
    source: {
      doc_id: `fc-${index}`,
      title: fc.claim_review_title || fc.claim,
      publisher: fc.publisher_name,
      url: fc.claim_review_url,
      published_at: fc.claim_date,
      retrieved_at: null,
      source_type: "factcheck",
      source_name: fc.publisher_site,
      rating: fc.rating,
    },
  };
}

/** Adapt a raw backend CheckResponse into the shape the UI expects. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function adaptResponse(raw: any): CheckResponse {
  const verdict = mapVerdict(raw.verdict ?? raw.verdict_label);
  const confidence: number | null = raw.confidence ?? null;
  const justification: string | null = raw.justification ?? null;
  const factChecks: FactCheckResult[] = raw.fact_check_results ?? [];
  const sourceArticles: SourceRef[] = raw.source_articles ?? [];

  const claims: ClaimResult[] =
    raw.claims && Array.isArray(raw.claims) && raw.claims.length > 0
      ? raw.claims
      : verdict
        ? [
            {
              id: raw.id,
              text: raw.input?.title ?? raw.input?.url ?? "Artykuł",
              verdict,
              confidence: confidence ?? 0,
              strength: {
                level: confidenceToLevel(confidence),
                score: confidence ?? 0,
                factors: [],
              },
              risk: confidence !== null && confidence < 0.5 ? "high" : "low",
              justification: justification ?? "",
              evidence: factChecks.map(factCheckToEvidence),
            },
          ]
        : [];

  const warnings: Warning[] =
    raw.warnings && Array.isArray(raw.warnings) ? raw.warnings : [];

  const moderatorCase: ModeratorCaseInfo = raw.moderator_case ?? { state: "none" };

  const relatedMaterials: SourceRef[] =
    raw.related_materials && Array.isArray(raw.related_materials)
      ? raw.related_materials
      : sourceArticles;

  const incidentMatches: IncidentMatch[] = raw.incident_matches ?? [];

  return {
    id: raw.id,
    created_at: raw.created_at,
    channel: raw.channel,
    status: raw.status,
    status_message: raw.status_message ?? null,
    error_code: raw.error_code ?? null,
    input: { ...raw.input, kind: raw.input?.kind ?? "url" },
    claims,
    verdict,
    verdict_label: verdict,
    confidence,
    justification,
    summary: raw.summary ?? justification,
    keywords: raw.keywords ?? [],
    main_topic: raw.main_topic ?? "",
    fact_check_results: factChecks,
    source_articles: sourceArticles,
    related_materials: relatedMaterials,
    incident_matches: incidentMatches,
    limitations: raw.limitations ?? [],
    warnings,
    moderator_case: moderatorCase,
    meta: raw.meta ?? {
      duration_ms: 0,
      stages_ms: {},
      provider: null,
      model: null,
      bielik_model: null,
      llm_calls: 0,
      tokens_in: 0,
      tokens_out: 0,
      cost_usd: null,
      processing_location: "",
      cached: false,
    },
  };
}

async function getAdapted(path: string, options?: RequestOptions): Promise<CheckResponse> {
  const raw = await getJson<unknown>(path, options);
  return adaptResponse(raw);
}

// --- Public API ---

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson("/health", { signal });
}

export async function createCheck(
  body: CheckRequest,
  signal?: AbortSignal,
): Promise<CheckResponse> {
  // Backend only accepts URL checks; if only text was provided without a URL, return a helpful error.
  if (!body.url) {
    throw new ApiError("validation", {
      detail: "Podaj link do artykułu, który chcesz sprawdzić.",
    });
  }
  return getAdapted("/checks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: body.url, session_id: body.session_id }),
    timeoutMs: CHECK_TIMEOUT_MS,
    signal,
  });
}

export async function createImageCheck(
  file: File,
  sessionId: string | undefined,
  signal?: AbortSignal,
): Promise<CheckResponse> {
  const form = new FormData();
  form.append("file", file);
  if (sessionId) form.append("session_id", sessionId);
  // No Content-Type header: the browser sets the multipart boundary itself.
  return getAdapted("/checks/image", {
    method: "POST",
    body: form,
    timeoutMs: CHECK_TIMEOUT_MS,
    signal,
  });
}

export function getCheck(id: string, signal?: AbortSignal): Promise<CheckResponse> {
  return getAdapted(`/checks/${encodeURIComponent(id)}`, { signal });
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

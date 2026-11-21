// Mirrors backend/app/schemas.py. Dates and datetimes arrive as ISO strings.

export type Verdict =
  | "potwierdzone"
  | "falszywe"
  | "wprowadzajace_w_blad"
  | "brak_wystarczajacych_dowodow"
  | "nie_podlega_weryfikacji";

export type CheckStatus =
  | "completed"
  | "needs_clarification"
  | "out_of_scope"
  | "error";

export type SourceType =
  | "official"
  | "legal"
  | "statistics"
  | "international"
  | "factcheck"
  | "media";

export type Stance = "supports" | "refutes" | "context";

export type RetrievalMode = "hybrid" | "bm25" | "none";

export type RiskLevel = "standard" | "high";

export interface SourceRef {
  doc_id: string;
  title: string;
  publisher: string;
  url: string;
  published_at: string | null;
  retrieved_at: string | null;
  source_type: SourceType;
  source_name: string;
  language: string;
  license: string;
  claim_reviewed: string | null;
  rating: string | null;
}

export interface Evidence {
  id: string;
  stance: Stance;
  quote: string;
  source: SourceRef;
  archival: boolean;
}

export type StrengthEffect = "plus" | "minus" | "neutral";

export interface StrengthFactor {
  code: string;
  label: string;
  value: string;
  effect: StrengthEffect;
}

export type StrengthLevel = "mocna" | "umiarkowana" | "slaba" | "brak";

export interface Strength {
  level: StrengthLevel;
  score: number;
  factors: StrengthFactor[];
}

export interface ClaimResult {
  id: string;
  text: string;
  verdict: Verdict;
  verdict_label: string;
  justification: string;
  strength: Strength;
  evidence: Evidence[];
  conflict: boolean;
  missing: string | null;
  risk: RiskLevel;
}

export type WarningCode =
  | "injection_detected"
  | "archival_material"
  | "source_status"
  | "incident_match"
  | "pii_masked"
  | "retrieval_degraded"
  | "image_limits"
  | "input_truncated";

export interface Warning {
  code: WarningCode;
  message: string;
}

export interface IncidentMatch {
  incident_id: string;
  match_type: "url" | "domain" | "content";
  title: string;
  publisher: string;
  url: string;
  date: string | null;
  note: string;
}

export interface ModeratorCaseInfo {
  state: "none" | "recommended" | "created" | "updated";
  case_id: number | null;
  occurrences: number | null;
  notified: boolean;
  message: string;
}

export interface InputInfo {
  kind: "text" | "url" | "image";
  text: string;
  url: string | null;
  title: string | null;
  image_metadata: Record<string, string> | null;
}

export interface CheckMeta {
  duration_ms: number;
  stages_ms: Record<string, number>;
  provider: string | null;
  model: string | null;
  llm_calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
  retrieval_mode: RetrievalMode;
  corpus_version: string;
  processing_location: string;
  cached: boolean;
}

export interface CheckResponse {
  id: string;
  created_at: string;
  channel: string;
  status: CheckStatus;
  status_message: string | null;
  error_code: string | null;
  input: InputInfo;
  summary: string | null;
  claims: ClaimResult[];
  warnings: Warning[];
  incident_matches: IncidentMatch[];
  related_materials: SourceRef[];
  moderator_case: ModeratorCaseInfo;
  limitations: string[];
  meta: CheckMeta;
}

export interface CheckRequest {
  text?: string | null;
  url?: string | null;
  session_id?: string | null;
}

export type StoragePolicy = "full_text" | "excerpt" | "structured";

export interface SourceCatalogEntry {
  id: string;
  name: string;
  publisher: string;
  homepage: string;
  source_type: SourceType;
  tier: number;
  language: string;
  license: string;
  storage: StoragePolicy;
  qualification: string;
  update_policy: string;
  enabled: boolean;
  disabled_reason: string | null;
  documents: number;
  newest: string | null;
}

export interface CorpusStats {
  documents: number;
  passages: number;
  domains: number;
  by_type: Record<string, number>;
  version: string;
  built_at: string | null;
}

export interface SourcesResponse {
  sources: SourceCatalogEntry[];
  corpus: CorpusStats;
  rules: string[];
}

export interface HealthResponse {
  status: "ok" | "degraded";
  llm_provider: string;
  llm_model: string | null;
  llm_configured: boolean;
  retrieval_mode: RetrievalMode;
  corpus: CorpusStats;
  processing_location: string;
  retention_days: number;
}

export interface SmsMessage {
  id: number;
  direction: "in" | "out";
  body: string;
  created_at: string;
  check_id: string | null;
}

export interface SmsThread {
  messages: SmsMessage[];
}

export type CaseStatus = "open" | "in_review" | "resolved";

export interface CaseOut {
  id: number;
  created_at: string;
  updated_at: string;
  claim_text: string;
  status: CaseStatus;
  risk: RiskLevel;
  occurrences: number;
  channels: string[];
  notified_at: string | null;
  note: string;
  check_ids: string[];
}

export interface CaseUpdate {
  status?: CaseStatus | null;
  note?: string | null;
}

export interface SecurityEventOut {
  id: number;
  created_at: string;
  kind: string;
  origin: string;
  detail: string;
  check_id: string | null;
}

export interface CheckListItem {
  id: string;
  created_at: string;
  channel: string;
  status: CheckStatus;
  input_kind: string;
  input_preview: string;
  verdicts: Verdict[];
  duration_ms: number;
  cost_usd: number | null;
}

export interface MetricsResponse {
  checks_total: number;
  by_status: Record<string, number>;
  by_channel: Record<string, number>;
  by_verdict: Record<string, number>;
  abstention_rate: number | null;
  median_duration_ms: number | null;
  p95_duration_ms: number | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd_total: number | null;
  cost_usd_per_1000: number | null;
  errors: Record<string, number>;
  security_events: Record<string, number>;
  open_cases: number;
}

export interface SessionDeleteResponse {
  deleted: number;
}

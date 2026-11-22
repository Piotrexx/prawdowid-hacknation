// Mirrors backend/app/schemas.py. Dates and datetimes arrive as ISO strings.

// --- Verdict & related enums ---

export type Verdict =
  | "potwierdzone"
  | "falszywe"
  | "wprowadzajace_w_blad"
  | "brak_wystarczajacych_dowodow"
  | "nie_podlega_weryfikacji";

export type VerdictLabel = Verdict;

export type StrengthLevel = "mocna" | "umiarkowana" | "slaba" | "brak";
export type Stance = "supports" | "refutes" | "context";
export type SourceType = "official" | "legal" | "statistics" | "international" | "factcheck" | "media";
export type StoragePolicy = "full_text" | "excerpt" | "structured";
export type RetrievalMode = "hybrid" | "bm25" | "none";

export type WarningCode =
  | "pii_masked"
  | "incident_match"
  | "archival_material"
  | "injection_detected"
  | "source_status"
  | "retrieval_degraded"
  | "image_limits"
  | "image_manipulation"
  | "image_edit_software"
  | "ai_generated"
  | "ai_edited"
  | "content_credentials"
  | "input_truncated";

export interface Warning {
  code: WarningCode;
  message: string;
}

export interface ModeratorCaseInfo {
  state: "none" | "recommended" | "created" | "updated";
  case_id?: number | null;
  message?: string | null;
  occurrences?: number | null;
  notified?: boolean;
}

// --- Evidence & Claims ---

export interface EvidenceSource {
  doc_id: string;
  title: string;
  publisher: string;
  url: string;
  published_at: string | null;
  retrieved_at: string | null;
  source_type: string;
  source_name: string;
  rating: string | null;
}

export interface Evidence {
  id: string;
  stance: Stance;
  source: EvidenceSource;
}

export type StrengthEffect = "plus" | "minus" | "neutral";

export interface StrengthFactor {
  code: string;
  label: string;
  value: string;
  effect: StrengthEffect;
}

export interface Strength {
  level: StrengthLevel;
  score: number;
  factors: StrengthFactor[];
}

export interface ClaimResult {
  id: string;
  text: string;
  verdict: Verdict;
  confidence: number;
  strength: Strength;
  risk: "high" | "medium" | "low";
  justification: string;
  evidence: Evidence[];
}

// --- Incident matches ---

export interface IncidentMatch {
  incident_id: string;
  match_type: "url" | "domain" | "content";
  note: string;
  url: string;
  title: string;
  publisher: string;
  date: string | null;
}

// --- Core API types ---

export type CheckStatus =
  | "completed"
  | "needs_clarification"
  | "out_of_scope"
  | "error";

export interface SourceRef {
  doc_id: string;
  title: string;
  publisher: string;
  url: string;
  published_at: string | null;
  retrieved_at: string | null;
  source_type: string;
  source_name: string;
  rating: string | null;
  license?: string | null;
  claim_reviewed?: string | null;
}

export interface FactCheckResult {
  claim: string;
  claimant: string | null;
  claim_date: string | null;
  claim_review_url: string;
  claim_review_title: string;
  publisher_name: string;
  publisher_site: string;
  rating: string;
  textual_rating: string | null;
  url: string;
}

export interface InputInfo {
  kind: "url" | "text" | "image";
  text: string;
  url: string;
  title: string | null;
}

export interface CheckMeta {
  duration_ms: number;
  stages_ms: Record<string, number>;
  provider: string | null;
  model: string | null;
  bielik_model: string | null;
  llm_calls: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
  processing_location: string;
  cached: boolean;
}

export interface ClarifyingQuestion {
  text: string;
  /** Ready answers the user can pick with one click; empty when the question is open. */
  options: string[];
}

export interface ClarificationExchange {
  questions: string[];
  answer: string;
}

/** `questions` is non-empty only while the check waits for an answer (needs_clarification). */
export interface Clarification {
  questions: ClarifyingQuestion[];
  missing: string[];
  round: number;
  max_rounds: number;
  history: ClarificationExchange[];
}

export interface CheckResponse {
  id: string;
  created_at: string;
  channel: string;
  status: CheckStatus;
  status_message: string | null;
  error_code: string | null;
  input: InputInfo;
  // Claims: each distinct claim in the input, with its own verdict
  claims: ClaimResult[];
  // Single top-level verdict (legacy compat – also set when there is exactly one claim)
  verdict: Verdict | null;
  verdict_label: string | null;
  confidence: number | null;
  justification: string | null;
  summary: string | null;
  keywords: string[];
  main_topic: string;
  fact_check_results: FactCheckResult[];
  source_articles: SourceRef[];
  related_materials: SourceRef[];
  incident_matches: IncidentMatch[];
  limitations: string[];
  warnings: Warning[];
  moderator_case: ModeratorCaseInfo;
  /** The check whose question this one answers. */
  parent_check_id: string | null;
  clarification: Clarification | null;
  meta: CheckMeta;
}

export interface CheckRequest {
  url?: string;
  text?: string;
  /** Set when `text` answers the clarifying question of that check. */
  parent_check_id?: string | null;
  session_id?: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  llm_provider: string;
  llm_model: string | null;
  bielik_model: string | null;
  llm_configured: boolean;
  bielik_configured: boolean;
  google_factcheck_configured: boolean;
  processing_location: string;
  retention_days: number;
}

export interface AdminMetrics {
  checks_total: number;
  by_status: Record<string, number>;
  by_channel: Record<string, number>;
  by_verdict: Record<string, number>;
  avg_factchecks: number;
  median_duration_ms: number | null;
  errors: Record<string, number>;
}

export interface AdminCheckItem {
  id: string;
  created_at: string;
  channel: string;
  status: string;
  url: string | null;
  title: string | null;
  verdict: string | null;
  confidence: number | null;
  keywords: string[];
  factcheck_count: number;
  duration_ms: number | null;
}

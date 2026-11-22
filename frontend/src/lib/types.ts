// Mirrors backend/app/schemas.py. Dates and datetimes arrive as ISO strings.
//
// The verdict comes in two layers, as in the backend:
//  * `claims` — each claim judged on its own, from quotes verified against the
//    source catalogue (`evidence`). This is the evidence layer and it decides.
//  * `verdict` / `confidence` / `fact_check_results` — a summary of the whole
//    material plus Google Fact Check Tools matches. Supporting layer only.

// --- Verdict & related enums ---

export type Verdict =
  | "potwierdzone"
  | "falszywe"
  | "wprowadzajace_w_blad"
  | "brak_wystarczajacych_dowodow"
  | "nie_podlega_weryfikacji";

export type StrengthLevel = "mocna" | "umiarkowana" | "slaba" | "brak";
export type Stance = "supports" | "refutes" | "context";
export type SourceType = "official" | "legal" | "statistics" | "international" | "factcheck" | "media" | "reverse_image";
export type RetrievalMode = "hybrid" | "bm25" | "none";
export type Risk = "standard" | "high";

export type WarningCode =
  | "pii_masked"
  | "incident_match"
  | "archival_material"
  | "injection_detected"
  | "source_status"
  | "retrieval_degraded"
  | "image_limits"
  | "audio_limits"
  | "input_truncated"
  | "factcheck_unavailable"
  | "keywords_degraded"
  | "transcription_unavailable"
  | "image_manipulation"
  | "image_edit_software"
  | "ai_generated"
  | "ai_edited"
  | "content_credentials"
  | "image_analysis_unavailable";

export interface Warning {
  code: WarningCode;
  message: string;
}

export interface ModeratorCaseInfo {
  state: "none" | "recommended" | "created" | "updated";
  case_id?: number | null;
  occurrences?: number | null;
  notified?: boolean;
  message?: string;
}

// --- Sources & evidence ---

export interface SourceRef {
  doc_id: string;
  title: string;
  publisher: string;
  url: string;
  published_at: string | null;
  retrieved_at: string | null;
  source_type: SourceType;
  source_name: string;
  license?: string;
  claim_reviewed?: string | null;
  rating?: string | null;
}

/** Kept as an alias: the evidence source is a plain SourceRef. */
export type EvidenceSource = SourceRef;

export interface Evidence {
  id: string;
  stance: Stance;
  /** Verbatim fragment of the source, verified automatically by the backend. */
  quote: string;
  source: SourceRef;
  archival?: boolean;
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
  verdict_label: string;
  justification: string;
  strength: Strength;
  evidence: Evidence[];
  conflict: boolean;
  missing: string | null;
  risk: Risk;
}

// --- Incident matches ---

export interface IncidentMatch {
  incident_id: string;
  match_type: "url" | "domain" | "content";
  title: string;
  publisher: string;
  url: string;
  date: string | null;
  note: string;
}

// --- Supporting layer ---

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
  url: string | null;
}

// --- Core API types ---

export type CheckStatus =
  | "completed"
  | "needs_clarification"
  | "out_of_scope"
  | "error";

export interface InputInfo {
  kind: "text" | "url" | "image" | "audio";
  text: string;
  url?: string | null;
  title?: string | null;
  image_metadata?: Record<string, string> | null;
  audio_metadata?: Record<string, string> | null;
}

// --- Image analysis (reverse search, copy comparison, AI provenance) ---

export type ImageRelation =
  | "identical"
  | "locally_modified"
  | "different_version"
  | "not_comparable"
  | "not_downloaded";

export interface EngineStatus {
  engine: string;
  ok: boolean;
  results: number;
  error: string | null;
}

export interface ImageMatch {
  engine: string;
  page_url: string;
  image_url: string | null;
  thumbnail_url: string | null;
  title: string | null;
  domain: string | null;
  first_seen: string | null;
  relation: ImageRelation;
  difference: number | null;
}

export interface ImageRegion {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface AiSignal {
  source: "c2pa" | "iptc" | "generator_metadata";
  kind: "ai_generated" | "ai_edited";
  detail: string;
  generator: string | null;
  signed: boolean;
}

export interface AiAssessment {
  result: "ai_generated" | "ai_edited" | "predates_generative_ai" | "no_signals";
  signals: AiSignal[];
  content_credentials: string | null;
}

export interface ImageAnalysis {
  assessment:
    | "manipulation_suspected"
    | "consistent_with_copies"
    | "insufficient_copies"
    | "no_matches";
  sha256: string;
  width: number;
  height: number;
  engines: EngineStatus[];
  matches_found: number;
  compared: number;
  identical: number;
  locally_modified: number;
  different_versions: number;
  earliest_seen: string | null;
  changed_regions: ImageRegion[];
  exif: Record<string, string>;
  ai: AiAssessment | null;
  matches: ImageMatch[];
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
  bielik_tokens_in: number;
  bielik_tokens_out: number;
  cost_usd: number | null;
  retrieval_mode: RetrievalMode;
  corpus_version: string;
  processing_location: string;
  cached: boolean;
  related_count?: number;
  embedding_model?: string | null;
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
  // --- evidence layer (decisive) ---
  claims: ClaimResult[];
  warnings: Warning[];
  incident_matches: IncidentMatch[];
  related_materials: SourceRef[];
  moderator_case: ModeratorCaseInfo;
  // --- supporting layer ---
  verdict: Verdict | null;
  verdict_label: string | null;
  confidence: number | null;
  justification: string | null;
  keywords: string[];
  main_topic: string;
  fact_check_results: FactCheckResult[];
  source_articles: SourceRef[];
  limitations: string[];
  image_analysis: ImageAnalysis | null;
  meta: CheckMeta;
}

export interface CheckRequest {
  url?: string;
  text?: string;
  session_id?: string | null;
}

// --- Privacy consent ---

export interface ConsentRequest {
  session_id: string;
  policy_version: string;
  accepted: boolean;
}

export interface ConsentResponse {
  session_id: string;
  policy_version: string;
  accepted: boolean;
  recorded_at: string;
}

// --- Corpus & health ---

export interface CorpusStats {
  documents: number;
  passages: number;
  domains: number;
  by_type: Record<string, number>;
  version: string;
  built_at: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  llm_provider: string;
  llm_model: string | null;
  bielik_model: string | null;
  llm_configured: boolean;
  bielik_configured: boolean;
  google_factcheck_configured: boolean;
  retrieval_mode: RetrievalMode;
  corpus: CorpusStats;
  processing_location: string;
  retention_days: number;
  corpus_ready?: boolean;
  corpus_documents?: number;
  embedding_model?: string | null;
}

// --- Controlled archive ---

export interface ArchiveOut {
  id: string;
  check_id: string | null;
  created_at: string;
  retention_until: string;
  url: string | null;
  title: string | null;
  excerpt: string;
  content_hash: string;
  legal_basis: string;
}

// --- Moderator panel ---

export type CaseStatus = "open" | "in_review" | "resolved";

export interface CaseOut {
  id: number;
  created_at: string;
  updated_at: string;
  claim_text: string;
  status: CaseStatus;
  risk: Risk;
  occurrences: number;
  channels: string[];
  notified_at: string | null;
  note: string;
  check_ids: string[];
}

export interface CaseUpdate {
  status?: CaseStatus;
  note?: string;
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
  keywords: string[];
  factcheck_count: number;
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
  avg_factchecks: number;
  consents: number;
}

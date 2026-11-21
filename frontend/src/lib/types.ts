// Mirrors backend/app/schemas.py. Dates and datetimes arrive as ISO strings.

export type VerdictLabel =
  | "fake_news"
  | "prawdziwe"
  | "niepewne"
  | "satyna"
  | "opinia";

export type CheckStatus =
  | "completed"
  | "needs_clarification"
  | "out_of_scope"
  | "error";

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
}

export interface InputInfo {
  kind: "url";
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

export interface CheckResponse {
  id: string;
  created_at: string;
  channel: string;
  status: CheckStatus;
  status_message: string | null;
  error_code: string | null;
  input: InputInfo;
  verdict: VerdictLabel | null;
  verdict_label: string | null;
  confidence: number | null;
  justification: string | null;
  keywords: string[];
  main_topic: string;
  fact_check_results: FactCheckResult[];
  source_articles: SourceRef[];
  limitations: string[];
  meta: CheckMeta;
}

export interface CheckRequest {
  url: string;
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
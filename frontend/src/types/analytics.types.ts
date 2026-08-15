// Types mirroring app/schemas/analytics.py (Step 12).

export type PipelineStage = "not_cloned" | "cloned" | "scanned" | "chunked" | "embedded" | "indexed";

export type HealthGrade = "A" | "B" | "C" | "D" | "F";

export type ActivityEventType =
  | "cloned"
  | "updated"
  | "scanned"
  | "chunked"
  | "embedded"
  | "indexed"
  | "chat_message";

export interface RepositoryOverview {
  repository_name: string;
  owner: string;
  repo: string;
  size_mb: number | null;
  age_days: number | null;
  cloned_at: string | null;
  last_updated_at: string | null;
  last_indexed_at: string | null;
  files_indexed: number;
  chunks_created: number;
  embeddings_generated: number;
  vector_count: number;
  health_score: number | null;
  pipeline_stage: PipelineStage;
}

export interface LanguageStat {
  language: string;
  file_count: number;
  percentage: number;
  lines_of_code: number;
}

export interface FileSizeEntry {
  relative_path: string;
  language: string;
  size_bytes: number;
  line_count: number;
}

export interface LanguageStatsResponse {
  success: boolean;
  repository_name: string;
  total_files: number;
  total_lines_of_code: number;
  languages: LanguageStat[];
  most_active_languages: string[];
  largest_files: FileSizeEntry[];
  smallest_files: FileSizeEntry[];
}

export interface HealthScoreBreakdown {
  documentation_score: number;
  structure_score: number;
  comments_score: number;
  complexity_score: number;
  test_coverage_score: number;
}

export interface HealthScoreResponse {
  success: boolean;
  repository_name: string;
  overall_score: number;
  grade: HealthGrade;
  breakdown: HealthScoreBreakdown;
  recommendations: string[];
  calculated_at: string;
}

export interface IndexStatus {
  repository_name: string;
  stage: PipelineStage;
  progress_percentage: number;
  files_indexed: number;
  chunks_created: number;
  embeddings_generated: number;
  vectors_indexed: number;
  last_indexed_at: string | null;
}

export interface ActivityEvent {
  repository_name: string;
  event_type: ActivityEventType;
  timestamp: string;
  detail: string;
}

export interface ActivityTimelineResponse {
  success: boolean;
  count: number;
  events: ActivityEvent[];
}

export interface QuestionFrequency {
  question: string;
  count: number;
}

export interface AIUsageInsights {
  total_chat_requests: number;
  total_conversations: number;
  average_response_time_seconds: number;
  average_retrieval_time_seconds: number;
  average_similarity_score: number;
  total_embeddings_generated: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  most_asked_questions: QuestionFrequency[];
}

export interface UsageResponse {
  success: boolean;
  scope: string;
  usage: AIUsageInsights;
  generated_at: string;
}

export interface DashboardTotals {
  total_repositories: number;
  total_files_indexed: number;
  total_chunks_created: number;
  total_embeddings_generated: number;
  total_vectors: number;
  average_health_score: number | null;
}

export interface DashboardResponse {
  success: boolean;
  totals: DashboardTotals;
  repositories: RepositoryOverview[];
  language_distribution: Record<string, number>;
  ai_usage: AIUsageInsights;
  recent_activity: ActivityEvent[];
  generated_at: string;
}

export interface RepositoryAnalyticsResponse {
  success: boolean;
  overview: RepositoryOverview;
  index_status: IndexStatus;
  language_stats: LanguageStatsResponse;
  health: HealthScoreResponse;
  generated_at: string;
}

// Types mirroring app/schemas/github.py, scanner.py, chunking.py,
// embedding.py, and vector_store.py on the backend.

export interface RepositoryInfo {
  repository_name: string;
  owner: string;
  repo: string;
  clone_url: string;
  local_path: string;
  current_branch: string | null;
  latest_commit_hash: string | null;
  latest_commit_message: string | null;
  size_mb: number | null;
  cloned_at: string | null;
  last_updated_at: string | null;
}

export interface CloneRepositoryResponse {
  success: boolean;
  operation: "cloned" | "updated" | "already_up_to_date";
  message: string;
  data: RepositoryInfo;
}

export interface RepositoryListResponse {
  success: boolean;
  count: number;
  repositories: RepositoryInfo[];
}

export interface ScanStatistics {
  repository_name: string;
  total_files: number;
  supported_files: number;
  ignored_files: number;
  programming_languages: string[];
  language_counts: Record<string, number>;
  total_lines_of_code: number;
  repository_size_bytes: number;
  repository_size_mb: number;
  scanned_at: string;
}

export interface ScannedFileSummary {
  repository_name: string;
  relative_path: string;
  absolute_path: string;
  language: string;
  extension: string;
  size_bytes: number;
  line_count: number;
  last_modified: string;
}

export interface ChunkStatistics {
  repository_name: string;
  processing_time_seconds: number;
  total_files: number;
  files_skipped: number;
  documents_created: number;
  chunks_created: number;
  average_chunk_size: number;
  largest_chunk: number;
  smallest_chunk: number;
  chunk_size_setting: number;
  chunk_overlap_setting: number;
  processed_at: string;
}

export interface EmbeddingStatistics {
  repository_name: string;
  provider: string;
  model: string;
  dimension: number;
  total_documents: number;
  embeddings_created: number;
  embeddings_failed: number;
  batches_processed: number;
  batch_size: number;
  total_processing_time_seconds: number;
  average_time_per_document_seconds: number;
  generated_at: string;
}

export interface VectorStatistics {
  repository_name: string;
  collection_name: string;
  total_vectors: number;
  dimension: number | null;
  distance_metric: string | null;
  language_counts: Record<string, number>;
  unique_files: number;
}

/** Which pipeline stages have completed for a repository, tracked client-side. */
export type PipelineStage =
  | "cloned"
  | "scanned"
  | "chunked"
  | "embedded"
  | "indexed";

export interface PipelineStatus {
  cloned: boolean;
  scanned: boolean;
  chunked: boolean;
  embedded: boolean;
  indexed: boolean;
}

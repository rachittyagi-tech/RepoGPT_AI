// Types mirroring app/schemas/chat.py and app/schemas/rag.py on the backend.

export type ChatRole = "user" | "assistant";

export interface SourceReference {
  repository_name: string;
  file_path: string;
  language: string;
  chunk_number: number;
  total_chunks: number;
  score: number;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
  sources?: SourceReference[];
  /** Client-side only: true while a streamed answer is still arriving. */
  streaming?: boolean;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatRequestPayload {
  repository_name: string;
  message: string;
  conversation_id?: string | null;
  top_k?: number;
  score_threshold?: number;
  language?: string;
  file_name?: string;
}

export interface ChatResponse {
  success: boolean;
  answer: string;
  repository_name: string;
  conversation_id: string;
  processing_time_seconds: number;
  token_usage: TokenUsage;
  sources: SourceReference[];
  similarity_scores: number[];
  created_at: string;
}

export interface HistoryResponse {
  success: boolean;
  conversation_id: string;
  repository_name: string;
  messages: {
    role: ChatRole;
    content: string;
    timestamp: string;
    sources: SourceReference[];
  }[];
  message_count: number;
}

export interface ChatModelInfo {
  name: string;
  display_name: string;
  max_output_tokens: number;
  status: "active" | "not_configured";
}

/** Parsed shape of the `event: done` SSE frame from POST /api/chat/stream. */
export interface ChatStreamDoneEvent {
  repository_name: string;
  conversation_id: string;
  processing_time_seconds: number;
  sources: SourceReference[];
  similarity_scores: number[];
}

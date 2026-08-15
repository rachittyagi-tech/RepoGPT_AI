// Shared envelope shapes returned by every RepoGPT AI backend module.

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  success: false;
  error: ApiError;
  request_id?: string;
  path?: string;
}

/** Type guard used by the axios error interceptor. */
export function isApiErrorResponse(data: unknown): data is ApiErrorResponse {
  return (
    typeof data === "object" &&
    data !== null &&
    "success" in data &&
    (data as { success: unknown }).success === false
  );
}

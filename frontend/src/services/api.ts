import axios, { AxiosError } from "axios";
import { API_BASE_URL } from "@/utils/constants";
import { isApiErrorResponse, type ApiError } from "@/types/api.types";

/**
 * A normalized error shape every service function throws, so components
 * never need to know whether a failure came from the network, from a
 * validation error, or from a backend domain exception.
 */
export class ApiRequestError extends Error {
  code: string;
  status: number | null;
  details?: Record<string, unknown>;

  constructor(message: string, code: string, status: number | null, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000, // repo cloning/scanning can legitimately take a while
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const data = error.response.data;
      if (isApiErrorResponse(data)) {
        const apiError: ApiError = data.error;
        return Promise.reject(
          new ApiRequestError(apiError.message, apiError.code, error.response.status, apiError.details)
        );
      }
      return Promise.reject(
        new ApiRequestError(
          `Request failed with status ${error.response.status}.`,
          "http_error",
          error.response.status
        )
      );
    }

    if (error.request) {
      return Promise.reject(
        new ApiRequestError(
          "Could not reach the RepoGPT AI backend. Is the server running?",
          "network_error",
          null
        )
      );
    }

    return Promise.reject(new ApiRequestError(error.message, "unknown_error", null));
  }
);

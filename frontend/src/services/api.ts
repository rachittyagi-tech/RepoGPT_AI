import axios, {
  AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";
import { API_BASE_URL, LOCAL_STORAGE_KEYS } from "@/utils/constants";
import { isApiErrorResponse, type ApiError } from "@/types/api.types";

/**
 * A normalized error shape every service function throws.
 */
export class ApiRequestError extends Error {
  code: string;
  status: number | null;
  details?: Record<string, unknown>;

  constructor(
    message: string,
    code: string,
    status: number | null,
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000,
  headers: {
    "Content-Type": "application/json",
  },
});

const getAccessToken = (): string | null =>
  localStorage.getItem(LOCAL_STORAGE_KEYS.accessToken);

const getRefreshToken = (): string | null =>
  localStorage.getItem(LOCAL_STORAGE_KEYS.refreshToken);

const saveTokens = (
  accessToken: string,
  refreshToken: string
): void => {
  localStorage.setItem(
    LOCAL_STORAGE_KEYS.accessToken,
    accessToken
  );

  localStorage.setItem(
    LOCAL_STORAGE_KEYS.refreshToken,
    refreshToken
  );
};

const clearTokens = (): void => {
  localStorage.removeItem(LOCAL_STORAGE_KEYS.accessToken);
  localStorage.removeItem(LOCAL_STORAGE_KEYS.refreshToken);
};

/**
 * Add the access token to protected API requests.
 */
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();

    if (
      token &&
      !config.url?.includes("/auth/login") &&
      !config.url?.includes("/auth/refresh")
    ) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  }
);

let refreshPromise: Promise<string | null> | null = null;

/**
 * Refresh the access token when the backend returns 401.
 */
const refreshAccessToken = async (): Promise<string | null> => {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    return null;
  }

  if (!refreshPromise) {
    refreshPromise = axios
      .post(
        `${API_BASE_URL}/api/auth/refresh`,
        {
          refresh_token: refreshToken,
        },
        {
          headers: {
            "Content-Type": "application/json",
          },
          timeout: 30_000,
        }
      )
      .then((response) => {
        const data = response.data as {
          access_token: string;
          refresh_token: string;
        };

        saveTokens(data.access_token, data.refresh_token);

        return data.access_token;
      })
      .catch(() => {
        clearTokens();
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
};

api.interceptors.response.use(
  (response) => response,

  async (error: AxiosError) => {
    const originalRequest = error.config as
      | (InternalAxiosRequestConfig & { _retry?: boolean })
      | undefined;

    /**
     * Automatically refresh an expired access token once.
     */
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/login") &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      originalRequest._retry = true;

      const newAccessToken = await refreshAccessToken();

      if (newAccessToken) {
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      }
    }

    if (error.response) {
      const data = error.response.data;

      if (isApiErrorResponse(data)) {
        const apiError: ApiError = data.error;

        return Promise.reject(
          new ApiRequestError(
            apiError.message,
            apiError.code,
            error.response.status,
            apiError.details
          )
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

    return Promise.reject(
      new ApiRequestError(
        error.message,
        "unknown_error",
        null
      )
    );
  }
);

export { clearTokens, saveTokens };
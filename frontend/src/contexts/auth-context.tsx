import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, clearTokens, saveTokens } from "@/services/api";
import { LOCAL_STORAGE_KEYS } from "@/utils/constants";

interface AuthUser {
  id: string;
  username: string;
  email: string;
  full_name: string;
  is_active?: boolean;
}

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    let accessToken = localStorage.getItem(
      LOCAL_STORAGE_KEYS.accessToken
    );

    const refreshToken = localStorage.getItem(
      LOCAL_STORAGE_KEYS.refreshToken
    );

    // No tokens means the user is logged out.
    if (!accessToken && !refreshToken) {
      setUser(null);
      return;
    }

    try {
      // If access token is missing, use refresh token first.
      if (!accessToken && refreshToken) {
        const response = await api.post<LoginResponse>(
          "/api/auth/refresh",
          {
            refresh_token: refreshToken,
          }
        );

        saveTokens(
          response.data.access_token,
          response.data.refresh_token
        );

        accessToken = response.data.access_token;
      }

      if (!accessToken) {
        clearTokens();
        setUser(null);
        return;
      }

      const response = await api.get<AuthUser>("/api/users/me");
      setUser(response.data);
    } catch {
      clearTokens();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const initializeAuth = async () => {
      try {
        await refreshUser();
      } finally {
        setIsLoading(false);
      }
    };

    void initializeAuth();
  }, [refreshUser]);

  const login = useCallback(
    async (identifier: string, password: string) => {
      const response = await api.post<LoginResponse>(
        "/api/auth/login",
        {
          identifier,
          password,
        }
      );

      saveTokens(
        response.data.access_token,
        response.data.refresh_token
      );

      await refreshUser();
    },
    [refreshUser]
  );

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem(
      LOCAL_STORAGE_KEYS.refreshToken
    );

    try {
      if (refreshToken) {
        await api.post("/api/auth/logout", {
          refresh_token: refreshToken,
        });
      }
    } finally {
      clearTokens();
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      login,
      logout,
      refreshUser,
    }),
    [user, isLoading, login, logout, refreshUser]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside an AuthProvider."
    );
  }

  return context;
}
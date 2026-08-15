import { api } from "./api";
import type {
  ActivityTimelineResponse,
  DashboardResponse,
  HealthScoreResponse,
  LanguageStatsResponse,
  RepositoryAnalyticsResponse,
  UsageResponse,
} from "@/types/analytics.types";

/**
 * Wraps the Repository Analytics & AI Insights Dashboard module (Step 12).
 * Every call here is read-only — none of them trigger a scan/chunk/embed/
 * index run; use `repositoryService` for that.
 */
export const analyticsService = {
  async dashboard(): Promise<DashboardResponse> {
    const { data } = await api.get("/api/analytics/dashboard");
    return data;
  },

  async repository(repositoryName: string): Promise<RepositoryAnalyticsResponse> {
    const { data } = await api.get(`/api/analytics/repository/${encodeURIComponent(repositoryName)}`);
    return data;
  },

  async languages(repositoryName: string): Promise<LanguageStatsResponse> {
    const { data } = await api.get(`/api/analytics/languages/${encodeURIComponent(repositoryName)}`);
    return data;
  },

  async health(repositoryName: string): Promise<HealthScoreResponse> {
    const { data } = await api.get(`/api/analytics/health/${encodeURIComponent(repositoryName)}`);
    return data;
  },

  async activity(limit = 50): Promise<ActivityTimelineResponse> {
    const { data } = await api.get("/api/analytics/activity", { params: { limit } });
    return data;
  },

  async usage(repositoryName?: string): Promise<UsageResponse> {
    const { data } = await api.get("/api/analytics/usage", {
      params: repositoryName ? { repository: repositoryName } : undefined,
    });
    return data;
  },
};

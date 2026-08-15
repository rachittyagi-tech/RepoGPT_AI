import { useQuery } from "@tanstack/react-query";
import { analyticsService } from "@/services/analytics.service";
import { QUERY_KEYS } from "@/utils/constants";

/** Full dashboard: totals, per-repo overviews, language distribution, AI usage, recent activity. */
export function useAnalyticsDashboard() {
  return useQuery({
    queryKey: QUERY_KEYS.analyticsDashboard,
    queryFn: () => analyticsService.dashboard(),
    refetchInterval: 30_000, // pipeline stages / chat usage can change in the background
  });
}

/** Combined overview + index status + language stats + health for one repository. */
export function useRepositoryAnalytics(repositoryName: string | null) {
  return useQuery({
    queryKey: QUERY_KEYS.analyticsRepository(repositoryName ?? ""),
    queryFn: () => analyticsService.repository(repositoryName as string),
    enabled: Boolean(repositoryName),
  });
}

export function useLanguageStats(repositoryName: string | null) {
  return useQuery({
    queryKey: QUERY_KEYS.analyticsLanguages(repositoryName ?? ""),
    queryFn: () => analyticsService.languages(repositoryName as string),
    enabled: Boolean(repositoryName),
    select: (data) => data,
  });
}

export function useRepositoryHealth(repositoryName: string | null) {
  return useQuery({
    queryKey: QUERY_KEYS.analyticsHealth(repositoryName ?? ""),
    queryFn: () => analyticsService.health(repositoryName as string),
    enabled: Boolean(repositoryName),
  });
}

export function useActivityTimeline(limit = 50) {
  return useQuery({
    queryKey: QUERY_KEYS.analyticsActivity,
    queryFn: () => analyticsService.activity(limit),
    refetchInterval: 30_000,
  });
}

/** AI usage insights — scoped to one repository, or `null` for usage across all repos. */
export function useAIUsage(repositoryName: string | null) {
  return useQuery({
    queryKey: QUERY_KEYS.analyticsUsage(repositoryName),
    queryFn: () => analyticsService.usage(repositoryName ?? undefined),
    refetchInterval: 30_000,
  });
}

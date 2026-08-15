import { useState } from "react";
import { BarChart3 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { RepositoryOverview } from "@/components/analytics/repository-overview";
import { RepositoryStats } from "@/components/analytics/repository-stats";
import { IndexStatusCard } from "@/components/analytics/index-status-card";
import { LanguageChart } from "@/components/analytics/language-chart";
import { HealthScoreCard } from "@/components/analytics/health-score-card";
import { ActivityTimeline } from "@/components/analytics/activity-timeline";
import { AIUsageCard } from "@/components/analytics/ai-usage-card";
import {
  useAnalyticsDashboard,
  useRepositoryAnalytics,
  useActivityTimeline,
  useAIUsage,
} from "@/hooks/use-analytics";
import { useRepositoryContext } from "@/contexts/repository-context";
import { formatNumber, displayRepoName } from "@/utils/format";
import { cn } from "@/utils/cn";
import type { DashboardTotals } from "@/types/analytics.types";

function DashboardTotalsRow({ totals }: { totals: DashboardTotals }) {
  const items = [
    { label: "Repositories", value: formatNumber(totals.total_repositories) },
    { label: "Files indexed", value: formatNumber(totals.total_files_indexed) },
    { label: "Chunks created", value: formatNumber(totals.total_chunks_created) },
    { label: "Embeddings", value: formatNumber(totals.total_embeddings_generated) },
    { label: "Vectors", value: formatNumber(totals.total_vectors) },
    {
      label: "Avg health",
      value: totals.average_health_score !== null ? `${totals.average_health_score.toFixed(0)}/100` : "—",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {items.map((item) => (
        <Card key={item.label}>
          <CardContent className="p-4">
            <p className="font-mono text-xl font-semibold">{item.value}</p>
            <p className="mt-1 text-xs text-muted">{item.label}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const { activeRepository } = useRepositoryContext();
  const [selectedRepo, setSelectedRepo] = useState<string | null>(activeRepository);

  const dashboard = useAnalyticsDashboard();
  const repoAnalytics = useRepositoryAnalytics(selectedRepo);
  const activity = useActivityTimeline();
  const usage = useAIUsage(selectedRepo);

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4 sm:p-6">
      <div className="flex items-center gap-2">
        <BarChart3 className="h-5 w-5 text-mint" aria-hidden="true" />
        <div>
          <h1 className="text-xl font-semibold">Analytics</h1>
          <p className="mt-1 text-sm text-muted">
            Repository health, indexing status, language breakdowns, and AI usage insights.
          </p>
        </div>
      </div>

      {/* ---- Dashboard totals ---- */}
      {dashboard.isLoading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : dashboard.isError || !dashboard.data ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted">
            Couldn't load the dashboard. Is the backend running?
          </CardContent>
        </Card>
      ) : (
        <DashboardTotalsRow totals={dashboard.data.totals} />
      )}

      {/* ---- Repository selector ---- */}
      {dashboard.data && dashboard.data.repositories.length > 0 && (
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Select a repository">
          {dashboard.data.repositories.map((repo) => (
            <button
              key={repo.repository_name}
              role="tab"
              aria-selected={selectedRepo === repo.repository_name}
              onClick={() => setSelectedRepo(repo.repository_name)}
              className={cn(
                "rounded-sm border px-3 py-1.5 text-xs font-mono transition-colors",
                selectedRepo === repo.repository_name
                  ? "border-mint/40 bg-mint/10 text-mint"
                  : "border-border text-muted hover:bg-surface-hover hover:text-foreground"
              )}
            >
              {displayRepoName(repo.repository_name)}
            </button>
          ))}
        </div>
      )}

      {/* ---- Selected repository detail ---- */}
      {selectedRepo ? (
        repoAnalytics.isLoading ? (
          <Skeleton className="h-96 w-full" />
        ) : repoAnalytics.isError || !repoAnalytics.data ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted">
              Couldn't load analytics for <Badge variant="outline">{displayRepoName(selectedRepo)}</Badge>.
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-4">
            <RepositoryOverview overview={repoAnalytics.data.overview} />
            <RepositoryStats overview={repoAnalytics.data.overview} />
            <div className="grid gap-4 lg:grid-cols-2">
              <IndexStatusCard status={repoAnalytics.data.index_status} />
              <HealthScoreCard health={repoAnalytics.data.health} />
            </div>
            <LanguageChart stats={repoAnalytics.data.language_stats} />
          </div>
        )
      ) : (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted">
            Clone a repository from the Dashboard to see its analytics here.
          </CardContent>
        </Card>
      )}

      {/* ---- AI usage + activity (repo-scoped when one is selected, else global) ---- */}
      <div className="grid gap-4 lg:grid-cols-2">
        <AIUsageCard usage={usage.data?.usage} isLoading={usage.isLoading} />
        <ActivityTimeline events={activity.data?.events} isLoading={activity.isLoading} />
      </div>
    </div>
  );
}

import { FolderGit2, HardDrive, Calendar, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatBytes, formatDate, formatRelativeTime, displayRepoName } from "@/utils/format";
import type { PipelineStage, RepositoryOverview as RepositoryOverviewType } from "@/types/analytics.types";

const STAGE_LABEL: Record<PipelineStage, string> = {
  not_cloned: "Not cloned",
  cloned: "Cloned",
  scanned: "Scanned",
  chunked: "Chunked",
  embedded: "Embedded",
  indexed: "Indexed",
};

const STAGE_VARIANT: Record<PipelineStage, "default" | "mint" | "amber" | "danger" | "outline"> = {
  not_cloned: "outline",
  cloned: "outline",
  scanned: "amber",
  chunked: "amber",
  embedded: "amber",
  indexed: "mint",
};

interface RepositoryOverviewProps {
  overview: RepositoryOverviewType;
}

/** Identity + lifecycle card for one repository: owner/repo, size, age, and where it
 * currently sits in the clone -> scan -> chunk -> embed -> index pipeline. */
export function RepositoryOverview({ overview }: RepositoryOverviewProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div className="flex items-center gap-2">
          <FolderGit2 className="h-4 w-4 text-mint" aria-hidden="true" />
          <CardTitle>{displayRepoName(overview.repository_name)}</CardTitle>
        </div>
        <Badge variant={STAGE_VARIANT[overview.pipeline_stage]}>{STAGE_LABEL[overview.pipeline_stage]}</Badge>
      </CardHeader>

      <CardContent className="grid gap-3 sm:grid-cols-2">
        <div className="flex items-center gap-2 text-sm">
          <HardDrive className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
          <span className="text-muted">Size</span>
          <span className="ml-auto font-mono">{formatBytes((overview.size_mb ?? 0) * 1024 * 1024)}</span>
        </div>

        <div className="flex items-center gap-2 text-sm">
          <Calendar className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
          <span className="text-muted">Age</span>
          <span className="ml-auto font-mono">
            {overview.age_days !== null ? `${overview.age_days}d` : "—"}
          </span>
        </div>

        <div className="flex items-center gap-2 text-sm">
          <Clock className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
          <span className="text-muted">Cloned</span>
          <span className="ml-auto font-mono text-xs" title={formatDate(overview.cloned_at)}>
            {formatRelativeTime(overview.cloned_at)}
          </span>
        </div>

        <div className="flex items-center gap-2 text-sm">
          <Clock className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
          <span className="text-muted">Last indexed</span>
          <span className="ml-auto font-mono text-xs" title={formatDate(overview.last_indexed_at)}>
            {overview.last_indexed_at ? formatRelativeTime(overview.last_indexed_at) : "Never"}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

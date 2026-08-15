import { Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/utils/cn";
import { formatNumber, formatRelativeTime } from "@/utils/format";
import type { IndexStatus, PipelineStage } from "@/types/analytics.types";

const STAGES: { key: PipelineStage; label: string }[] = [
  { key: "cloned", label: "Cloned" },
  { key: "scanned", label: "Scanned" },
  { key: "chunked", label: "Chunked" },
  { key: "embedded", label: "Embedded" },
  { key: "indexed", label: "Indexed" },
];

const STAGE_ORDER: PipelineStage[] = ["not_cloned", "cloned", "scanned", "chunked", "embedded", "indexed"];

interface IndexStatusCardProps {
  status: IndexStatus | undefined;
  isLoading?: boolean;
}

/** Shows exactly where a repository sits in the clone -> scan -> chunk -> embed ->
 * index pipeline, with a progress percentage and per-stage output counts. */
export function IndexStatusCard({ status, isLoading }: IndexStatusCardProps) {
  if (isLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (!status) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Index status</CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-sm text-muted">Not available.</CardContent>
      </Card>
    );
  }

  const currentIndex = STAGE_ORDER.indexOf(status.stage);

  const counts = [
    { label: "Files", value: status.files_indexed },
    { label: "Chunks", value: status.chunks_created },
    { label: "Embeddings", value: status.embeddings_generated },
    { label: "Vectors", value: status.vectors_indexed },
  ];

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Index status</CardTitle>
        <span className="font-mono text-xs text-muted">{status.progress_percentage.toFixed(0)}%</span>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-hover">
          <div
            className="h-full rounded-full bg-mint transition-all"
            style={{ width: `${status.progress_percentage}%` }}
          />
        </div>

        <ol
          className="flex flex-wrap items-center gap-0 font-mono text-xs"
          aria-label="Processing pipeline status"
        >
          {STAGES.map((stage, index) => {
            const stageIndex = STAGE_ORDER.indexOf(stage.key);
            const done = stageIndex <= currentIndex;
            const isActive = stageIndex === currentIndex;
            return (
              <li key={stage.key} className="flex items-center">
                <div
                  className={cn(
                    "flex items-center gap-1.5 rounded-sm border px-2 py-1 transition-colors",
                    done
                      ? isActive
                        ? "border-mint/30 bg-mint/10 text-mint"
                        : "border-border text-muted"
                      : "border-border text-muted"
                  )}
                >
                  {done ? (
                    isActive ? (
                      <Check className="h-3 w-3" aria-hidden="true" />
                    ) : (
                      <Check className="h-3 w-3 opacity-50" aria-hidden="true" />
                    )
                  ) : (
                    <span className="h-3 w-3 rounded-full border border-current" aria-hidden="true" />
                  )}
                  {stage.label}
                </div>
                {index < STAGES.length - 1 && (
                  <span className="mx-1 h-px w-3 bg-border" aria-hidden="true" />
                )}
              </li>
            );
          })}
        </ol>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {counts.map((c) => (
            <div key={c.label} className="rounded-sm border border-border p-2 text-center">
              <p className="font-mono text-sm font-semibold">{formatNumber(c.value)}</p>
              <p className="text-[11px] text-muted">{c.label}</p>
            </div>
          ))}
        </div>

        <p className="text-xs text-muted">
          Last indexed:{" "}
          <span className="font-mono">
            {status.last_indexed_at ? formatRelativeTime(status.last_indexed_at) : "Never"}
          </span>
        </p>
      </CardContent>
    </Card>
  );
}

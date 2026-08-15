import { Card, CardContent } from "@/components/ui/card";
import { formatNumber } from "@/utils/format";
import type { RepositoryOverview } from "@/types/analytics.types";

interface RepositoryStatsProps {
  overview: RepositoryOverview;
}

/** Pipeline-output metric grid for one repository: files indexed, chunks created,
 * embeddings generated, vector count, and overall health score. */
export function RepositoryStats({ overview }: RepositoryStatsProps) {
  const metrics = [
    { label: "Files indexed", value: formatNumber(overview.files_indexed) },
    { label: "Chunks created", value: formatNumber(overview.chunks_created) },
    { label: "Embeddings", value: formatNumber(overview.embeddings_generated) },
    { label: "Vectors", value: formatNumber(overview.vector_count) },
    {
      label: "Health score",
      value: overview.health_score !== null ? `${overview.health_score.toFixed(0)}/100` : "—",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      {metrics.map((metric) => (
        <Card key={metric.label}>
          <CardContent className="p-4">
            <p className="font-mono text-xl font-semibold sm:text-2xl">{metric.value}</p>
            <p className="mt-1 text-xs text-muted">{metric.label}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

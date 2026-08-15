import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { useVectorStatistics } from "@/hooks/use-repositories";
import { formatNumber } from "@/utils/format";

export function RepositoryStats({ repositoryName }: { repositoryName: string }) {
  const { data: stats, isLoading, isError } = useVectorStatistics(repositoryName);

  if (isLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
        This repository hasn't been fully processed yet — run the pipeline to see statistics.
      </div>
    );
  }

  const metrics = [
    { label: "Total vectors", value: formatNumber(stats.total_vectors) },
    { label: "Unique files", value: formatNumber(stats.unique_files) },
    { label: "Dimension", value: stats.dimension ?? "—" },
    { label: "Distance metric", value: stats.distance_metric ?? "—" },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent className="p-4">
              <p className="font-mono text-2xl font-semibold">{metric.value}</p>
              <p className="mt-1 text-xs text-muted">{metric.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Language breakdown</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {Object.entries(stats.language_counts).map(([language, count]) => (
            <Badge key={language} variant="outline">
              {language} · {count}
            </Badge>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

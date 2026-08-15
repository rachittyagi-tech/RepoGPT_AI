import { RadialBar, RadialBarChart, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/utils/cn";
import type { HealthGrade, HealthScoreResponse } from "@/types/analytics.types";

const GRADE_VARIANT: Record<HealthGrade, "mint" | "amber" | "danger"> = {
  A: "mint",
  B: "mint",
  C: "amber",
  D: "amber",
  F: "danger",
};

const BREAKDOWN_LABELS: { key: keyof HealthScoreResponse["breakdown"]; label: string }[] = [
  { key: "documentation_score", label: "Documentation" },
  { key: "structure_score", label: "Code structure" },
  { key: "comments_score", label: "Comments" },
  { key: "complexity_score", label: "Complexity" },
  { key: "test_coverage_score", label: "Test coverage" },
];

function scoreBarColor(score: number): string {
  if (score >= 75) return "bg-mint";
  if (score >= 45) return "bg-amber";
  return "bg-danger";
}

interface HealthScoreCardProps {
  health: HealthScoreResponse | undefined;
  isLoading?: boolean;
}

/** Repository Health Meter: an overall 0-100 heuristic score with a letter grade,
 * a radial gauge, a per-category breakdown, and actionable recommendations. */
export function HealthScoreCard({ health, isLoading }: HealthScoreCardProps) {
  if (isLoading) {
    return <Skeleton className="h-80 w-full" />;
  }

  if (!health) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Repository health</CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-sm text-muted">
          Health data isn't available yet — scan the repository first.
        </CardContent>
      </Card>
    );
  }

  const gaugeData = [{ name: "score", value: health.overall_score, fill: "hsl(156 55% 60%)" }];

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle>Repository health</CardTitle>
        <Badge variant={GRADE_VARIANT[health.grade]}>Grade {health.grade}</Badge>
      </CardHeader>

      <CardContent className="grid gap-6 sm:grid-cols-2">
        <div className="flex flex-col items-center justify-center">
          <div className="relative h-40 w-40" role="img" aria-label={`Overall health score ${health.overall_score} out of 100`}>
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                data={gaugeData}
                innerRadius="75%"
                outerRadius="100%"
                startAngle={90}
                endAngle={-270}
                barSize={12}
              >
                <RadialBar dataKey="value" background cornerRadius={8} max={100} />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-3xl font-semibold">{health.overall_score.toFixed(0)}</span>
              <span className="text-xs text-muted">/ 100</span>
            </div>
          </div>
        </div>

        <div className="flex flex-col justify-center gap-3">
          {BREAKDOWN_LABELS.map(({ key, label }) => {
            const score = health.breakdown[key];
            return (
              <div key={key}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="text-muted">{label}</span>
                  <span className="font-mono">{score.toFixed(0)}</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-hover">
                  <div
                    className={cn("h-full rounded-full transition-all", scoreBarColor(score))}
                    style={{ width: `${Math.max(score, 2)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>

      {health.recommendations.length > 0 && (
        <CardContent className="border-t border-border pt-4">
          <p className="mb-2 text-xs font-semibold text-muted">Recommendations</p>
          <ul className="flex flex-col gap-1.5 text-sm">
            {health.recommendations.map((rec) => (
              <li key={rec} className="flex gap-2">
                <span className="text-mint" aria-hidden="true">
                  →
                </span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  );
}

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/utils/format";
import type { LanguageStatsResponse } from "@/types/analytics.types";

// A small fixed palette, mapped by index rather than by language name, so
// colors stay stable across repositories without needing a lookup table
// for every possible language.
const CHART_COLORS = [
  "hsl(156 55% 60%)", // mint
  "hsl(42 78% 55%)", // amber
  "hsl(210 70% 60%)",
  "hsl(280 60% 65%)",
  "hsl(4 70% 60%)", // danger
  "hsl(190 60% 55%)",
  "hsl(320 55% 62%)",
  "hsl(90 45% 50%)",
];

interface LanguageChartProps {
  stats: LanguageStatsResponse | undefined;
  isLoading?: boolean;
}

/** Pie chart + table breakdown of a repository's (or the whole dashboard's) programming
 * language distribution, by file count. */
export function LanguageChart({ stats, isLoading }: LanguageChartProps) {
  if (isLoading) {
    return <Skeleton className="h-72 w-full" />;
  }

  if (!stats || stats.languages.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Languages</CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-sm text-muted">
          No language data yet — scan the repository first.
        </CardContent>
      </Card>
    );
  }

  const chartData = stats.languages.map((lang) => ({ name: lang.language, value: lang.file_count }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Languages</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-2">
        <div className="h-64 w-full" role="img" aria-label="Language distribution pie chart">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                innerRadius={50}
                outerRadius={90}
                paddingAngle={2}
              >
                {chartData.map((entry, index) => (
                  <Cell key={entry.name} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--surface))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 6,
                  fontSize: 12,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <ul className="flex flex-col justify-center gap-2 text-sm">
          {stats.languages.map((lang, index) => (
            <li key={lang.language} className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                aria-hidden="true"
              />
              <span className="flex-1 truncate">{lang.language}</span>
              <span className="font-mono text-xs text-muted">
                {formatNumber(lang.file_count)} files · {lang.percentage.toFixed(1)}%
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDuration, formatNumber } from "@/utils/format";
import type { AIUsageInsights } from "@/types/analytics.types";

interface AIUsageCardProps {
  usage: AIUsageInsights | undefined;
  isLoading?: boolean;
}

/** AI Chat Engine usage insights: request volume, timing, retrieval quality, token
 * usage/estimated cost, and the most frequently asked questions. */
export function AIUsageCard({ usage, isLoading }: AIUsageCardProps) {
  if (isLoading) {
    return <Skeleton className="h-96 w-full" />;
  }

  if (!usage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>AI usage</CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-sm text-muted">Not available.</CardContent>
      </Card>
    );
  }

  const metrics = [
    { label: "Chat requests", value: formatNumber(usage.total_chat_requests) },
    { label: "Conversations", value: formatNumber(usage.total_conversations) },
    { label: "Avg response time", value: formatDuration(usage.average_response_time_seconds) },
    { label: "Avg retrieval time", value: formatDuration(usage.average_retrieval_time_seconds) },
    { label: "Avg similarity", value: usage.average_similarity_score.toFixed(3) },
    { label: "Total tokens", value: formatNumber(usage.total_tokens) },
    { label: "Est. cost", value: `$${usage.estimated_cost_usd.toFixed(4)}` },
    { label: "Embeddings", value: formatNumber(usage.total_embeddings_generated) },
  ];

  const questionData = usage.most_asked_questions.slice(0, 5).map((q) => ({
    question: q.question.length > 28 ? `${q.question.slice(0, 28)}…` : q.question,
    fullQuestion: q.question,
    count: q.count,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI usage</CardTitle>
      </CardHeader>

      <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-sm border border-border p-3">
            <p className="font-mono text-lg font-semibold">{metric.value}</p>
            <p className="mt-0.5 text-[11px] text-muted">{metric.label}</p>
          </div>
        ))}
      </CardContent>

      <CardContent className="border-t border-border pt-4">
        <p className="mb-3 text-xs font-semibold text-muted">Most asked questions</p>
        {questionData.length === 0 ? (
          <p className="text-sm text-muted">No chat activity recorded yet.</p>
        ) : (
          <div className="h-48 w-full" role="img" aria-label="Most asked questions bar chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={questionData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="question"
                  width={140}
                  tick={{ fontSize: 11 }}
                  interval={0}
                />
                <Tooltip
                  formatter={(value: number) => [value, "Asked"]}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullQuestion ?? ""}
                  contentStyle={{
                    background: "hsl(var(--surface))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" fill="hsl(156 55% 60%)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

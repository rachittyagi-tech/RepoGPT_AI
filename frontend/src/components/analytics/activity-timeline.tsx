import { Download, RefreshCw, Database, MessageSquare, ScanLine, Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatRelativeTime, displayRepoName } from "@/utils/format";
import type { ActivityEvent, ActivityEventType } from "@/types/analytics.types";

const EVENT_ICON: Record<ActivityEventType, typeof Download> = {
  cloned: Download,
  updated: RefreshCw,
  scanned: ScanLine,
  chunked: Layers,
  embedded: Layers,
  indexed: Database,
  chat_message: MessageSquare,
};

interface ActivityTimelineProps {
  events: ActivityEvent[] | undefined;
  isLoading?: boolean;
}

/** Chronological feed of clone/update/index events across every repository, most recent first. */
export function ActivityTimeline({ events, isLoading }: ActivityTimelineProps) {
  if (isLoading) {
    return <Skeleton className="h-64 w-full" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent activity</CardTitle>
      </CardHeader>
      <CardContent>
        {!events || events.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">No activity recorded yet.</p>
        ) : (
          <ol className="flex flex-col gap-4">
            {events.map((event, index) => {
              const Icon = EVENT_ICON[event.event_type];
              return (
                <li key={`${event.repository_name}-${event.timestamp}-${index}`} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border bg-surface-hover">
                      <Icon className="h-3.5 w-3.5 text-mint" aria-hidden="true" />
                    </span>
                    {index < events.length - 1 && <span className="mt-1 w-px flex-1 bg-border" />}
                  </div>
                  <div className="min-w-0 flex-1 pb-1">
                    <p className="text-sm">
                      <span className="font-medium">{displayRepoName(event.repository_name)}</span>{" "}
                      <span className="text-muted">— {event.detail}</span>
                    </p>
                    <p className="mt-0.5 text-xs text-muted" title={formatDate(event.timestamp)}>
                      {formatRelativeTime(event.timestamp)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

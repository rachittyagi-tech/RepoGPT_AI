import { Check, Loader2 } from "lucide-react";
import { cn } from "@/utils/cn";
import type { PipelineStatus } from "@/types/repository.types";

const STAGES: { key: keyof PipelineStatus; label: string }[] = [
  { key: "cloned", label: "Cloned" },
  { key: "scanned", label: "Scanned" },
  { key: "chunked", label: "Chunked" },
  { key: "embedded", label: "Embedded" },
  { key: "indexed", label: "Indexed" },
];

interface PipelineStatusRailProps {
  status: PipelineStatus;
  /** Stage currently in flight, if a pipeline run is active. */
  activeStage?: keyof PipelineStatus | null;
}

/**
 * Renders the repository's progress through the actual backend pipeline
 * (Steps 3-7) as a horizontal rail of monospace stage labels — grounded
 * directly in this product's real architecture rather than a decorative
 * numbered list.
 */
export function PipelineStatusRail({ status, activeStage }: PipelineStatusRailProps) {
  return (
    <ol className="flex items-center gap-0 font-mono text-xs" aria-label="Processing pipeline status">
      {STAGES.map((stage, index) => {
        const done = status[stage.key];
        const isActive = activeStage === stage.key;
        return (
          <li key={stage.key} className="flex items-center">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-sm border px-2 py-1 transition-colors",
                done
                  ? "border-mint/30 bg-mint/10 text-mint"
                  : isActive
                    ? "border-amber/30 bg-amber/10 text-amber"
                    : "border-border text-muted"
              )}
            >
              {done ? (
                <Check className="h-3 w-3" aria-hidden="true" />
              ) : isActive ? (
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
              ) : (
                <span className="h-3 w-3 rounded-full border border-current" aria-hidden="true" />
              )}
              {stage.label}
            </div>
            {index < STAGES.length - 1 && <span className="mx-1 h-px w-3 bg-border" aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}

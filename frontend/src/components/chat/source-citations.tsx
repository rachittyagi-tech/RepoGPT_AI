import { FileCode2, Layers3 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { SourceReference } from "@/types/chat.types";

interface SourceCitationsProps {
  sources: SourceReference[];
}

export function SourceCitations({
  sources,
}: SourceCitationsProps) {
  if (!sources.length) {
    return null;
  }

  return (
    <section
      aria-label="Sources used for this answer"
      className="mt-4 rounded-lg border border-border/60 bg-surface/40 p-3"
    >
      <div className="mb-2.5 flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-md border border-amber/20 bg-amber/[0.08]">
          <Layers3 className="h-3.5 w-3.5 text-amber" />
        </div>

        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-foreground">
            Sources
          </p>
          <p className="text-[10px] text-muted">
            Files used to ground this answer
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {sources.map((source, index) => (
          <Badge
            key={`${source.file_path}-${index}`}
            variant="amber"
            title={`Relevance score: ${source.score.toFixed(2)}`}
            className="max-w-full"
          >
            <FileCode2 className="h-3 w-3 shrink-0" />

            <span className="min-w-0 max-w-[260px] truncate sm:max-w-[360px]">
              {source.file_path}
            </span>
          </Badge>
        ))}
      </div>
    </section>
  );
}

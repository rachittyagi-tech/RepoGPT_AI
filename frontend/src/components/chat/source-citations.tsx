import { FileCode2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { SourceReference } from "@/types/chat.types";

/** Renders the file citations an answer was grounded in, with relevance scores. */
export function SourceCitations({ sources }: { sources: SourceReference[] }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="font-mono text-[11px] text-muted">Sources:</span>
      {sources.map((source, i) => (
        <Badge key={`${source.file_path}-${i}`} variant="amber" title={`Relevance: ${source.score.toFixed(2)}`}>
          <FileCode2 className="h-3 w-3" />
          {source.file_path}
        </Badge>
      ))}
    </div>
  );
}

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, FileCode2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { repositoryService } from "@/services/repository.service";
import { QUERY_KEYS } from "@/utils/constants";
import { formatBytes } from "@/utils/format";

export function RepositoryExplorer({ repositoryName }: { repositoryName: string }) {
  const [search, setSearch] = useState("");
  const [languageFilter, setLanguageFilter] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: QUERY_KEYS.files(repositoryName),
    queryFn: () => repositoryService.getFiles(repositoryName),
    enabled: Boolean(repositoryName),
  });

  const files = data?.files ?? [];

  const languages = useMemo(
    () => Array.from(new Set(files.map((f) => f.language))).sort(),
    [files]
  );

  const filteredFiles = useMemo(() => {
    return files.filter((file) => {
      const matchesSearch = file.relative_path.toLowerCase().includes(search.toLowerCase());
      const matchesLanguage = !languageFilter || file.language === languageFilter;
      return matchesSearch && matchesLanguage;
    });
  }, [files, search, languageFilter]);

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
        This repository hasn't been scanned yet — run the pipeline first.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search files by path…"
            className="pl-9 font-mono"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button onClick={() => setLanguageFilter(null)}>
            <Badge variant={languageFilter === null ? "mint" : "outline"}>All</Badge>
          </button>
          {languages.map((language) => (
            <button key={language} onClick={() => setLanguageFilter(language)}>
              <Badge variant={languageFilter === language ? "mint" : "outline"}>{language}</Badge>
            </button>
          ))}
        </div>
      </div>

      <div className="divide-y divide-border rounded-md border border-border">
        {filteredFiles.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted">No files match your search.</p>
        ) : (
          filteredFiles.map((file) => (
            <div
              key={file.relative_path}
              className="flex items-center gap-3 px-3 py-2 text-sm hover:bg-surface-hover"
            >
              <FileCode2 className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate font-mono text-xs">{file.relative_path}</span>
              <Badge variant="outline" className="shrink-0">
                {file.language}
              </Badge>
              <span className="w-16 shrink-0 text-right font-mono text-xs text-muted">
                {formatBytes(file.size_bytes)}
              </span>
              <span className="w-14 shrink-0 text-right font-mono text-xs text-muted">
                {file.line_count} ln
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

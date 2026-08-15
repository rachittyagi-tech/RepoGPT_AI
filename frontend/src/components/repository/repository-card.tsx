import { Link } from "react-router-dom";
import { GitBranch, GitCommitHorizontal, HardDrive, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { displayRepoName, formatBytes, formatRelativeTime } from "@/utils/format";
import { useRepositoryContext } from "@/contexts/repository-context";
import { useDeleteRepository } from "@/hooks/use-repositories";
import type { RepositoryInfo } from "@/types/repository.types";

export function RepositoryCard({ repository }: { repository: RepositoryInfo }) {
  const { setActiveRepository } = useRepositoryContext();
  const deleteRepository = useDeleteRepository();

  return (
    <Card className="group transition-colors hover:border-mint/40">
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div className="min-w-0">
          <Link
            to="/repository"
            onClick={() => setActiveRepository(repository.repository_name)}
            className="truncate font-mono text-sm font-semibold hover:text-mint"
          >
            {displayRepoName(repository.repository_name)}
          </Link>
          {repository.latest_commit_message && (
            <p className="mt-1 truncate text-xs text-muted">{repository.latest_commit_message}</p>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Delete ${repository.repository_name}`}
          onClick={() => deleteRepository.mutate(repository.repository_name)}
          loading={deleteRepository.isPending}
          className="opacity-0 group-hover:opacity-100"
        >
          <Trash2 className="h-4 w-4 text-danger" />
        </Button>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-4 font-mono text-xs text-muted">
        {repository.current_branch && (
          <span className="flex items-center gap-1">
            <GitBranch className="h-3.5 w-3.5" /> {repository.current_branch}
          </span>
        )}
        {repository.latest_commit_hash && (
          <span className="flex items-center gap-1">
            <GitCommitHorizontal className="h-3.5 w-3.5" />
            {repository.latest_commit_hash.slice(0, 7)}
          </span>
        )}
        <span className="flex items-center gap-1">
          <HardDrive className="h-3.5 w-3.5" />
          {formatBytes(repository.size_mb ? repository.size_mb * 1024 * 1024 : null)}
        </span>
        <span className="ml-auto">{formatRelativeTime(repository.last_updated_at)}</span>
      </CardContent>
    </Card>
  );
}

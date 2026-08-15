import { FolderGit2 } from "lucide-react";
import { motion } from "framer-motion";
import { RepositoryCard } from "./repository-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRepositories } from "@/hooks/use-repositories";

function RepositoryListSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-32 w-full" />
      ))}
    </div>
  );
}

export function RepositoryList() {
  const { data: repositories, isLoading, isError, error } = useRepositories();

  if (isLoading) return <RepositoryListSkeleton />;

  if (isError) {
    return (
      <div className="rounded-md border border-danger/30 bg-danger/5 p-6 text-sm text-danger">
        Failed to load repositories: {error instanceof Error ? error.message : "Unknown error"}
      </div>
    );
  }

  if (!repositories || repositories.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-border py-16 text-center">
        <FolderGit2 className="h-8 w-8 text-muted" aria-hidden="true" />
        <p className="text-sm font-medium">No repositories yet</p>
        <p className="max-w-xs text-xs text-muted">
          Paste a public GitHub repository URL above to clone your first one.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {repositories.map((repository, index) => (
        <motion.div
          key={repository.repository_name}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: index * 0.03 }}
        >
          <RepositoryCard repository={repository} />
        </motion.div>
      ))}
    </div>
  );
}

import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { RepositoryExplorer } from "@/components/repository/repository-explorer";
import { useRepositoryContext } from "@/contexts/repository-context";
import { displayRepoName } from "@/utils/format";

export default function ExplorerPage() {
  const { activeRepository } = useRepositoryContext();
  const navigate = useNavigate();

  if (!activeRepository) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-muted">No repository selected.</p>
        <Button onClick={() => navigate("/")}>Go to Dashboard</Button>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 sm:p-6">
      <div>
        <h1 className="font-mono text-xl font-semibold">{displayRepoName(activeRepository)}</h1>
        <p className="mt-1 text-sm text-muted">Browse and search every scanned source file.</p>
      </div>
      <RepositoryExplorer repositoryName={activeRepository} />
    </div>
  );
}

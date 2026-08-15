import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PlayCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PipelineStatusRail } from "@/components/repository/pipeline-status";
import { RepositoryStats } from "@/components/repository/repository-stats";
import { useRepositoryContext } from "@/contexts/repository-context";
import { useProcessRepository, useVectorStatistics } from "@/hooks/use-repositories";
import { displayRepoName } from "@/utils/format";
import type { PipelineStatus } from "@/types/repository.types";

export default function RepositoryPage() {
  const { activeRepository } = useRepositoryContext();
  const navigate = useNavigate();
  const processRepository = useProcessRepository();
  const { data: vectorStats } = useVectorStatistics(activeRepository);

  const [status, setStatus] = useState<PipelineStatus>({
    cloned: true,
    scanned: false,
    chunked: false,
    embedded: false,
    indexed: false,
  });
  const [activeStage, setActiveStage] = useState<keyof PipelineStatus | null>(null);

  // If this repository was already indexed in a prior session, reflect that immediately.
  useEffect(() => {
    if (vectorStats && vectorStats.total_vectors > 0) {
      setStatus({ cloned: true, scanned: true, chunked: true, embedded: true, indexed: true });
    }
  }, [vectorStats]);

  if (!activeRepository) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-muted">No repository selected.</p>
        <Button onClick={() => navigate("/")}>Go to Dashboard</Button>
      </div>
    );
  }

  const handleRunPipeline = () => {
    setActiveStage("scanned");
    processRepository.mutate({
      repositoryName: activeRepository,
      onProgress: (stage) => {
        setStatus((prev) => ({ ...prev, [stage]: true }));
        const next: Record<string, keyof PipelineStatus | null> = {
          scanned: "chunked",
          chunked: "embedded",
          embedded: "indexed",
          indexed: null,
        };
        setActiveStage(next[stage]);
      },
    });
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-mono text-xl font-semibold">{displayRepoName(activeRepository)}</h1>
          <p className="mt-1 text-sm text-muted">Processing pipeline &amp; statistics</p>
        </div>
        <Button onClick={handleRunPipeline} loading={processRepository.isPending}>
          <PlayCircle className="h-4 w-4" />
          {status.indexed ? "Re-run pipeline" : "Run pipeline"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Pipeline status</CardTitle>
        </CardHeader>
        <CardContent>
          <PipelineStatusRail
            status={status}
            activeStage={processRepository.isPending ? activeStage : null}
          />
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-muted">Statistics</h2>
        <RepositoryStats repositoryName={activeRepository} />
      </div>
    </div>
  );
}

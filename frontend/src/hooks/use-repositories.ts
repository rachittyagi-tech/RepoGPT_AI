import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { githubService } from "@/services/github.service";
import { repositoryService } from "@/services/repository.service";
import { QUERY_KEYS } from "@/utils/constants";
import { useToast } from "./use-toast";
import type { ApiRequestError } from "@/services/api";

/** All cloned repositories, refreshed on window focus (cheap call, keeps the dashboard current). */
export function useRepositories() {
  return useQuery({
    queryKey: QUERY_KEYS.repositories,
    queryFn: () => githubService.list(),
    select: (data) => data.repositories,
  });
}

/** Clones a new repository, then invalidates the repository list. */
export function useCloneRepository() {
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (repoUrl: string) => githubService.clone(repoUrl),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.repositories });
      toast.success("Repository cloned", data.data.repository_name);
    },
    onError: (error: ApiRequestError) => {
      toast.error("Clone failed", error.message);
    },
  });
}

export function useDeleteRepository() {
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: (repositoryName: string) => githubService.remove(repositoryName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.repositories });
      toast.success("Repository deleted");
    },
    onError: (error: ApiRequestError) => {
      toast.error("Delete failed", error.message);
    },
  });
}

/** Vector store statistics for one repository — only meaningful once it's indexed. */
export function useVectorStatistics(repositoryName: string | null) {
  return useQuery({
    queryKey: QUERY_KEYS.vectorStats(repositoryName ?? ""),
    queryFn: () => repositoryService.vectorStatistics(repositoryName as string),
    enabled: Boolean(repositoryName),
    select: (data) => data.statistics,
    retry: false, // a 404 here just means "not indexed yet" — not worth retrying
  });
}

/** Runs scan -> chunk -> embed -> index for a repository, reporting stage progress. */
export function useProcessRepository() {
  const queryClient = useQueryClient();
  const toast = useToast();

  return useMutation({
    mutationFn: ({
      repositoryName,
      onProgress,
    }: {
      repositoryName: string;
      onProgress?: (stage: "scanned" | "chunked" | "embedded" | "indexed") => void;
    }) => repositoryService.runFullPipeline(repositoryName, onProgress),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.vectorStats(variables.repositoryName) });
      toast.success("Repository is chat-ready", variables.repositoryName);
    },
    onError: (error: ApiRequestError) => {
      toast.error("Processing failed", error.message);
    },
  });
}

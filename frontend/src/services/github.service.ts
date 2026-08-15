import { api } from "./api";
import type {
  CloneRepositoryResponse,
  RepositoryInfo,
  RepositoryListResponse,
} from "@/types/repository.types";

export const githubService = {
  async clone(repoUrl: string): Promise<CloneRepositoryResponse> {
    const { data } = await api.post<CloneRepositoryResponse>("/api/github/clone", {
      repo_url: repoUrl,
    });
    return data;
  },

  async update(repoUrl: string): Promise<CloneRepositoryResponse> {
    const { data } = await api.post<CloneRepositoryResponse>("/api/github/update", {
      repo_url: repoUrl,
    });
    return data;
  },

  async list(): Promise<RepositoryListResponse> {
    const { data } = await api.get<RepositoryListResponse>("/api/github/list");
    return data;
  },

  async status(repositoryName: string): Promise<{ success: boolean; data: RepositoryInfo }> {
    const { data } = await api.get(`/api/github/status/${encodeURIComponent(repositoryName)}`);
    return data;
  },

  async remove(repositoryName: string): Promise<{ success: boolean; message: string }> {
    const { data } = await api.delete(`/api/github/${encodeURIComponent(repositoryName)}`);
    return data;
  },
};

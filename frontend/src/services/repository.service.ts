import { api } from "./api";
import type {
  ChunkStatistics,
  EmbeddingStatistics,
  ScanStatistics,
  ScannedFileSummary,
  VectorStatistics,
} from "@/types/repository.types";

/**
 * Wraps the Scanner (Step 4), Chunking (Step 5), Embeddings (Step 6), and
 * Vector Store (Step 7) modules — the four backend stages a repository
 * moves through between "cloned" and "chat-ready".
 */
export const repositoryService = {
  async scan(repositoryName: string): Promise<{ success: boolean; statistics: ScanStatistics }> {
    const { data } = await api.post("/api/scanner/scan", { repository_name: repositoryName });
    return data;
  },

  async getFiles(
    repositoryName: string,
    language?: string
  ): Promise<{ success: boolean; count: number; files: ScannedFileSummary[] }> {
    const { data } = await api.get(`/api/scanner/files/${encodeURIComponent(repositoryName)}`, {
      params: { language, include_content: false },
    });
    return data;
  },

  async chunk(repositoryName: string): Promise<{ success: boolean; statistics: ChunkStatistics }> {
    const { data } = await api.post("/api/chunking/process", { repository_name: repositoryName });
    return data;
  },

  async embed(repositoryName: string): Promise<{ success: boolean; statistics: EmbeddingStatistics }> {
    const { data } = await api.post("/api/embeddings/generate", {
      repository_name: repositoryName,
      include_vectors: false, // frontend never needs raw vectors — keep the payload light
    });
    return data;
  },

  async index(
    repositoryName: string,
    forceRecreate = false
  ): Promise<{ success: boolean; message: string; statistics: unknown }> {
    const { data } = await api.post("/api/vector/index", {
      repository_name: repositoryName,
      force_recreate: forceRecreate,
    });
    return data;
  },

  async vectorStatistics(
    repositoryName: string
  ): Promise<{ success: boolean; statistics: VectorStatistics }> {
    const { data } = await api.get("/api/vector/statistics", {
      params: { repository_name: repositoryName },
    });
    return data;
  },

  /**
   * Runs scan -> chunk -> embed -> index sequentially, reporting progress
   * via `onProgress` after each stage completes. Each stage depends on the
   * previous one's cached result on the backend, so they must run in order.
   */
  async runFullPipeline(
    repositoryName: string,
    onProgress?: (stage: "scanned" | "chunked" | "embedded" | "indexed") => void
  ): Promise<void> {
    await this.scan(repositoryName);
    onProgress?.("scanned");

    await this.chunk(repositoryName);
    onProgress?.("chunked");

    await this.embed(repositoryName);
    onProgress?.("embedded");

    await this.index(repositoryName);
    onProgress?.("indexed");
  },
};

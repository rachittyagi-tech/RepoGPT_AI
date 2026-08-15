import { api } from "./api";

export interface CollectionInfo {
  collection_name: string;
  repository_name: string;
  vector_count: number;
  dimension: number | null;
  distance_metric: string | null;
}

/** Thin wrapper around /api/vector's collection-management endpoints. */
export const vectorService = {
  async listCollections(): Promise<{ success: boolean; count: number; collections: CollectionInfo[] }> {
    const { data } = await api.get("/api/vector/collections");
    return data;
  },

  async deleteCollection(collectionName: string): Promise<{ success: boolean; message: string }> {
    const { data } = await api.delete(`/api/vector/collection/${encodeURIComponent(collectionName)}`);
    return data;
  },
};

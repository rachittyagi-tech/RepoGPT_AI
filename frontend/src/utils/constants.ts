export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";

export const APP_NAME = "RepoGPT AI";

export const GITHUB_URL_PATTERN = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?$/;

export const QUERY_KEYS = {
  repositories: ["repositories"] as const,
  repositoryStats: (repo: string) => ["repository-stats", repo] as const,
  vectorStats: (repo: string) => ["vector-stats", repo] as const,
  files: (repo: string) => ["files", repo] as const,
  chatModels: ["chat-models"] as const,
  chatHistory: (conversationId: string) => ["chat-history", conversationId] as const,
  analyticsDashboard: ["analytics-dashboard"] as const,
  analyticsRepository: (repo: string) => ["analytics-repository", repo] as const,
  analyticsLanguages: (repo: string) => ["analytics-languages", repo] as const,
  analyticsHealth: (repo: string) => ["analytics-health", repo] as const,
  analyticsActivity: ["analytics-activity"] as const,
  analyticsUsage: (repo: string | null) => ["analytics-usage", repo ?? "all"] as const,
};

export const LOCAL_STORAGE_KEYS = {
  theme: "repogpt.theme",
  activeRepository: "repogpt.active-repository",
  activeConversation: "repogpt.active-conversation",
};

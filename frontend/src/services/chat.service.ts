import { api, ApiRequestError } from "./api";
import { API_BASE_URL } from "@/utils/constants";
import type {
  ChatModelInfo,
  ChatRequestPayload,
  ChatResponse,
  ChatStreamDoneEvent,
  HistoryResponse,
} from "@/types/chat.types";

export const chatService = {
  async send(payload: ChatRequestPayload): Promise<ChatResponse> {
    const { data } = await api.post<ChatResponse>("/api/chat", payload);
    return data;
  },

  async getHistory(conversationId: string): Promise<HistoryResponse> {
    const { data } = await api.get<HistoryResponse>("/api/chat/history", {
      params: { conversation_id: conversationId },
    });
    return data;
  },

  async clearHistory(conversationId: string): Promise<{ success: boolean; message: string }> {
    const { data } = await api.delete("/api/chat/history", {
      params: { conversation_id: conversationId },
    });
    return data;
  },

  async listModels(): Promise<{ success: boolean; active_model: string; models: ChatModelInfo[] }> {
    const { data } = await api.get("/api/chat/models");
    return data;
  },

  /**
   * Streams a chat answer via Server-Sent Events using the Fetch API
   * (axios doesn't expose a readable byte stream in the browser the way
   * `fetch` does). Parses `event: chunk` / `event: done` / `event: error`
   * frames as they arrive.
   */
  async stream(
    payload: ChatRequestPayload,
    handlers: {
      onChunk: (text: string) => void;
      onDone: (meta: ChatStreamDoneEvent) => void;
      onError: (error: ApiRequestError) => void;
      signal?: AbortSignal;
    }
  ): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: handlers.signal,
      });

      if (!response.ok || !response.body) {
        throw new ApiRequestError(
          `Stream request failed with status ${response.status}.`,
          "stream_error",
          response.status
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? ""; // last (possibly incomplete) frame stays in the buffer

        for (const frame of frames) {
          const eventMatch = frame.match(/^event:\s*(.+)$/m);
          const dataMatch = frame.match(/^data:\s*(.+)$/m);
          if (!eventMatch || !dataMatch) continue;

          const eventType = eventMatch[1].trim();
          const parsed = JSON.parse(dataMatch[1]);

          if (eventType === "chunk") {
            handlers.onChunk(parsed.text as string);
          } else if (eventType === "done") {
            handlers.onDone(parsed as ChatStreamDoneEvent);
          } else if (eventType === "error") {
            const err = parsed.error as { code: string; message: string };
            handlers.onError(new ApiRequestError(err.message, err.code, null));
          }
        }
      }
    } catch (error) {
      if (error instanceof ApiRequestError) {
        handlers.onError(error);
      } else if (error instanceof DOMException && error.name === "AbortError") {
        // Stream was intentionally cancelled — not an error the UI needs to surface.
      } else {
        handlers.onError(
          new ApiRequestError(
            error instanceof Error ? error.message : "Streaming failed unexpectedly.",
            "stream_error",
            null
          )
        );
      }
    }
  },
};

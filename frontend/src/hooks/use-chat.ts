import { useCallback, useRef, useState } from "react";
import { chatService } from "@/services/chat.service";
import type { ApiRequestError } from "@/services/api";
import { useToast } from "./use-toast";
import type { ChatMessage } from "@/types/chat.types";

interface UseChatOptions {
  repositoryName: string | null;
}

/**
 * Owns a single conversation's message list and the streaming lifecycle.
 * Kept local to the Chat page (not global context) — each mount starts
 * fresh unless a conversationId is restored, matching how a chat UI is
 * normally scoped to the page that renders it.
 */
export function useChat({ repositoryName }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const toast = useToast();

  const sendMessage = useCallback(
    async (text: string) => {
      if (!repositoryName || !text.trim() || isStreaming) return;

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text.trim(),
        timestamp: new Date().toISOString(),
      };
      const assistantMessageId = crypto.randomUUID();
      const assistantPlaceholder: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        streaming: true,
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      await chatService.stream(
        {
          repository_name: repositoryName,
          message: userMessage.content,
          conversation_id: conversationId,
        },
        {
          signal: controller.signal,
          onChunk: (text) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId ? { ...m, content: m.content + text } : m
              )
            );
          },
          onDone: (meta) => {
            setConversationId(meta.conversation_id);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, streaming: false, sources: meta.sources }
                  : m
              )
            );
            setIsStreaming(false);
          },
          onError: (error: ApiRequestError) => {
            setMessages((prev) => prev.filter((m) => m.id !== assistantMessageId));
            setIsStreaming(false);
            toast.error("Chat failed", error.message);
          },
        }
      );
    },
    [repositoryName, conversationId, isStreaming, toast]
  );

  const stopStreaming = useCallback(() => {
    abortControllerRef.current?.abort();
    setIsStreaming(false);
  }, []);

  const clearChat = useCallback(async () => {
    if (conversationId) {
      try {
        await chatService.clearHistory(conversationId);
      } catch {
        // Non-fatal — worst case the server keeps stale history under an ID we're abandoning anyway.
      }
    }
    setMessages([]);
    setConversationId(null);
  }, [conversationId]);

  return { messages, isStreaming, sendMessage, stopStreaming, clearChat, conversationId };
}

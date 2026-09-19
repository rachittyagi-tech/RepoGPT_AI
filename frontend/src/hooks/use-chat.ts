import { useCallback, useEffect, useRef, useState } from "react";

import { chatService } from "@/services/chat.service";

import type { ApiRequestError } from "@/services/api";

import { useToast } from "./use-toast";

import type { ChatMessage } from "@/types/chat.types";

import { LOCAL_STORAGE_KEYS } from "@/utils/constants";

import type { ConversationSummary } from "@/services/chat.service";

interface UseChatOptions {
  repositoryName: string | null;
}

interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatMessage["sources"];
  created_at?: string;
  timestamp?: string;
}

/**
 * Owns the active conversation, conversation list,
 * persisted history and streaming lifecycle.
 *
 * Responsibilities:
 * - Load conversation list
 * - Restore active conversation
 * - Load persisted messages
 * - Send streaming messages
 * - Switch conversations
 * - Start a new chat
 * - Delete conversations
 * - Clear conversation history
 * - Persist active conversation ID
 */
export function useChat({ repositoryName }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);

  const [conversations, setConversations] = useState<
    ConversationSummary[]
  >([]);

  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingConversations, setIsLoadingConversations] =
    useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const toast = useToast();

  /**
   * Save active conversation ID to localStorage.
   */
  const persistConversationId = useCallback((id: string | null) => {
    if (id) {
      localStorage.setItem(
        LOCAL_STORAGE_KEYS.activeConversation,
        id
      );
    } else {
      localStorage.removeItem(
        LOCAL_STORAGE_KEYS.activeConversation
      );
    }
  }, []);

  /**
   * Load conversations for the active repository.
   */
  const loadConversations = useCallback(async () => {
    if (!repositoryName) {
      setConversations([]);
      return;
    }

    setIsLoadingConversations(true);

    try {
      const response =
        await chatService.listConversations(repositoryName);

      setConversations(response.conversations ?? []);
    } catch (error) {
      const apiError = error as ApiRequestError;

      console.warn(
        "Unable to load conversations:",
        apiError?.message ?? error
      );

      setConversations([]);
    } finally {
      setIsLoadingConversations(false);
    }
  }, [repositoryName]);

  /**
   * Load a persisted conversation from backend.
   */
  const loadConversation = useCallback(
    async (id: string) => {
      if (!id) {
        return;
      }

      setIsLoadingHistory(true);

      try {
        const response =
          await chatService.getHistory(id);

        const historyMessages =
          (response.messages ?? []) as HistoryMessage[];

        const mappedMessages: ChatMessage[] =
          historyMessages.map((message) => ({
            id: message.id,
            role: message.role,
            content: message.content,
            timestamp:
              message.timestamp ??
              message.created_at ??
              new Date().toISOString(),
            sources: message.sources ?? [],
            streaming: false,
          }));

        setMessages(mappedMessages);
        setConversationId(id);
        persistConversationId(id);
      } catch (error) {
        const apiError = error as ApiRequestError;

        setMessages([]);
        setConversationId(null);
        persistConversationId(null);

        console.warn(
          "Unable to restore conversation:",
          apiError?.message ?? error
        );

        toast.error(
          "Conversation unavailable",
          "This conversation could not be loaded."
        );
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [persistConversationId, toast]
  );

  /**
   * Restore conversation list and active conversation
   * whenever the repository changes.
   *
   * IMPORTANT:
   * This effect intentionally does NOT depend on loadConversation.
   * This prevents a render/effect/API request loop when the
   * toast reference changes between renders.
   */
  useEffect(() => {
    if (!repositoryName) {
      setMessages([]);
      setConversationId(null);
      setConversations([]);
      persistConversationId(null);
      return;
    }

    let cancelled = false;

    const initializeChat = async () => {
      setIsLoadingConversations(true);

      try {
        /*
         * Load the conversation list exactly once
         * for this repository change.
         */
        const response =
          await chatService.listConversations(
            repositoryName
          );

        if (cancelled) {
          return;
        }

        const loadedConversations =
          response.conversations ?? [];

        setConversations(loadedConversations);

        /*
         * Restore previously active conversation.
         */
        const savedConversationId =
          localStorage.getItem(
            LOCAL_STORAGE_KEYS.activeConversation
          );

        const matchingConversation =
          savedConversationId
            ? loadedConversations.find(
                (conversation) =>
                  conversation.id ===
                  savedConversationId
              )
            : undefined;

        if (matchingConversation) {
          /*
           * Load history directly here instead of calling
           * loadConversation().
           *
           * This is important because loadConversation has
           * toast in its dependency chain.
           */
          setIsLoadingHistory(true);

          try {
            const historyResponse =
              await chatService.getHistory(
                matchingConversation.id
              );

            if (cancelled) {
              return;
            }

            const historyMessages =
              (historyResponse.messages ?? []) as HistoryMessage[];

            const mappedMessages: ChatMessage[] =
              historyMessages.map((message) => ({
                id: message.id,
                role: message.role,
                content: message.content,
                timestamp:
                  message.timestamp ??
                  message.created_at ??
                  new Date().toISOString(),
                sources: message.sources ?? [],
                streaming: false,
              }));

            setMessages(mappedMessages);
            setConversationId(
              matchingConversation.id
            );

            persistConversationId(
              matchingConversation.id
            );
          } finally {
            if (!cancelled) {
              setIsLoadingHistory(false);
            }
          }
        } else {
          setMessages([]);
          setConversationId(null);
          persistConversationId(null);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        const apiError = error as ApiRequestError;

        console.warn(
          "Unable to initialize conversations:",
          apiError?.message ?? error
        );

        setConversations([]);
        setMessages([]);
        setConversationId(null);

        persistConversationId(null);
      } finally {
        if (!cancelled) {
          setIsLoadingConversations(false);
        }
      }
    };

    void initializeChat();

    return () => {
      cancelled = true;
    };
  }, [repositoryName, persistConversationId]);

  /**
   * Send a message using streaming chat API.
   */
  const sendMessage = useCallback(
    async (text: string) => {
      if (
        !repositoryName ||
        !text.trim() ||
        isStreaming ||
        isLoadingHistory
      ) {
        return;
      }

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text.trim(),
        timestamp: new Date().toISOString(),
      };

      const assistantMessageId =
        crypto.randomUUID();

      const assistantPlaceholder: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        timestamp: new Date().toISOString(),
        streaming: true,
      };

      setMessages((prev) => [
        ...prev,
        userMessage,
        assistantPlaceholder,
      ]);

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
              prev.map((message) =>
                message.id === assistantMessageId
                  ? {
                      ...message,
                      content:
                        message.content + text,
                    }
                  : message
              )
            );
          },

          onDone: async (meta) => {
            setConversationId(
              meta.conversation_id
            );

            persistConversationId(
              meta.conversation_id
            );

            setMessages((prev) =>
              prev.map((message) =>
                message.id === assistantMessageId
                  ? {
                      ...message,
                      streaming: false,
                      sources: meta.sources ?? [],
                    }
                  : message
              )
            );

            setIsStreaming(false);
            abortControllerRef.current = null;

            /*
             * Refresh conversation list after
             * successful message completion.
             *
             * This is a single intentional request.
             */
            try {
              const response =
                await chatService.listConversations(
                  repositoryName
                );

              setConversations(
                response.conversations ?? []
              );
            } catch (error) {
              console.warn(
                "Unable to refresh conversations:",
                error
              );
            }
          },

          onError: (error: ApiRequestError) => {
            setMessages((prev) =>
              prev.filter(
                (message) =>
                  message.id !==
                  assistantMessageId
              )
            );

            setIsStreaming(false);
            abortControllerRef.current = null;

            toast.error(
              "Chat failed",
              error.message
            );
          },
        }
      );
    },
    [
      repositoryName,
      conversationId,
      isStreaming,
      isLoadingHistory,
      persistConversationId,
      toast,
    ]
  );

  /**
   * Stop active streaming response.
   */
  const stopStreaming = useCallback(() => {
    abortControllerRef.current?.abort();

    abortControllerRef.current = null;

    setIsStreaming(false);

    setMessages((prev) =>
      prev.map((message) =>
        message.streaming
          ? {
              ...message,
              streaming: false,
            }
          : message
      )
    );
  }, []);

  /**
   * Switch to another existing conversation.
   */
  const selectConversation = useCallback(
    async (id: string) => {
      if (!id) {
        return;
      }

      if (isStreaming) {
        abortControllerRef.current?.abort();
        abortControllerRef.current = null;
        setIsStreaming(false);
      }

      await loadConversation(id);
    },
    [isStreaming, loadConversation]
  );

  /**
   * Start a completely new conversation.
   */
  const newChat = useCallback(() => {
    if (isStreaming) {
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
    }

    setMessages([]);
    setConversationId(null);

    persistConversationId(null);
  }, [isStreaming, persistConversationId]);

  /**
   * Delete an existing conversation.
   */
  const deleteConversation = useCallback(
    async (id: string) => {
      if (!id) {
        return;
      }

      try {
        if (
          isStreaming &&
          id === conversationId
        ) {
          abortControllerRef.current?.abort();
          abortControllerRef.current = null;
          setIsStreaming(false);
        }

        await chatService.deleteConversation(id);

        setConversations((prev) =>
          prev.filter(
            (conversation) =>
              conversation.id !== id
          )
        );

        if (id === conversationId) {
          setMessages([]);
          setConversationId(null);

          persistConversationId(null);
        }
      } catch (error) {
        const apiError = error as ApiRequestError;

        toast.error(
          "Delete failed",
          apiError?.message ??
            "Unable to delete conversation."
        );
      }
    },
    [
      conversationId,
      isStreaming,
      persistConversationId,
      toast,
    ]
  );

  /**
   * Clear messages/history from the current conversation.
   */
  const clearChat = useCallback(async () => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    try {
      await chatService.clearHistory(
        conversationId
      );

      setMessages([]);

      await loadConversations();
    } catch (error) {
      const apiError = error as ApiRequestError;

      toast.error(
        "Clear failed",
        apiError?.message ??
          "Unable to clear conversation."
      );
    }
  }, [
    conversationId,
    loadConversations,
    toast,
  ]);

  return {
    messages,

    conversationId,

    conversations,

    isStreaming,
    isLoadingHistory,
    isLoadingConversations,

    sendMessage,
    stopStreaming,
    loadConversation,
    loadConversations,
    selectConversation,
    newChat,
    deleteConversation,
    clearChat,
  };
}
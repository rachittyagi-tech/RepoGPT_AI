import { useEffect, useRef } from "react";

import { MessageSquare } from "lucide-react";

import { ChatHeader } from "./chat-header";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { ConversationSidebar } from "./conversation-sidebar";

import { useChat } from "@/hooks/use-chat";
import { useRepositoryContext } from "@/contexts/repository-context";

import type { ConversationSummary } from "@/services/chat.service";

interface EmptyStateProps {
  message: string;
}

function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.08] bg-white/[0.03]">
        <MessageSquare className="h-6 w-6 text-slate-500" />
      </div>

      <p className="max-w-md text-sm leading-6 text-slate-500">
        {message}
      </p>
    </div>
  );
}

export function ChatWindow() {
  const {
    activeRepository,
    setActiveRepository,
  } = useRepositoryContext();

  const {
    messages,
    conversationId,
    conversations,
    isStreaming,
    isLoadingHistory,
    isLoadingConversations,
    sendMessage,
    stopStreaming,
    clearChat,
    selectConversation,
    newChat,
    deleteConversation,
  } = useChat({
    repositoryName: activeRepository,
  });

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const handleSelectConversation = async (
    conversation: ConversationSummary
  ) => {
    if (
      activeRepository &&
      conversation.repository_name !== activeRepository
    ) {
      setActiveRepository(conversation.repository_name);
    }

    await selectConversation(conversation.id);
  };

  return (
    <div className="flex h-full min-h-0 overflow-hidden">
      {/* Conversation Sidebar */}
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={conversationId}
        isLoading={isLoadingConversations}
        onNewChat={newChat}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={deleteConversation}
      />

      {/* Main Chat Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <ChatHeader
          activeRepository={activeRepository}
          onRepositoryChange={setActiveRepository}
          onClearChat={clearChat}
          hasMessages={messages.length > 0}
        />

        <div
          ref={scrollRef}
          className="min-h-0 flex-1 overflow-y-auto px-2 py-3 sm:px-4"
        >
          {!activeRepository ? (
            <EmptyState message="Select a repository above to start chatting." />
          ) : isLoadingHistory ? (
            <EmptyState message="Loading conversation..." />
          ) : messages.length === 0 ? (
            <EmptyState message="Ask anything about this repository — architecture, functions, classes, or APIs." />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-1">
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                />
              ))}
            </div>
          )}
        </div>

        <div className="mx-auto w-full max-w-3xl">
          <ChatInput
            onSend={sendMessage}
            onStop={stopStreaming}
            isStreaming={isStreaming}
            disabled={!activeRepository || isLoadingHistory}
          />
        </div>
      </div>
    </div>
  );
}
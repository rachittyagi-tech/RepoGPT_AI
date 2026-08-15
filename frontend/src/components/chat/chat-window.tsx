import { useEffect, useRef } from "react";
import { MessageSquare } from "lucide-react";
import { ChatHeader } from "./chat-header";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { useChat } from "@/hooks/use-chat";
import { useRepositoryContext } from "@/contexts/repository-context";

export function ChatWindow() {
  const { activeRepository, setActiveRepository } = useRepositoryContext();
  const { messages, isStreaming, sendMessage, stopStreaming, clearChat } = useChat({
    repositoryName: activeRepository,
  });
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto Scroll: always keep the latest message (or streaming token) in view.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex h-full flex-col">
      <ChatHeader
        activeRepository={activeRepository}
        onRepositoryChange={setActiveRepository}
        onClearChat={clearChat}
        hasMessages={messages.length > 0}
      />

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-2 py-3 sm:px-4">
        {!activeRepository ? (
          <EmptyState message="Select a repository above to start chatting." />
        ) : messages.length === 0 ? (
          <EmptyState message="Ask anything about this repository — architecture, functions, classes, or APIs." />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-1">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
          </div>
        )}
      </div>

      <div className="mx-auto w-full max-w-3xl">
        <ChatInput
          onSend={sendMessage}
          onStop={stopStreaming}
          isStreaming={isStreaming}
          disabled={!activeRepository}
        />
      </div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <MessageSquare className="h-8 w-8 text-muted" aria-hidden="true" />
      <p className="max-w-xs text-sm text-muted">{message}</p>
    </div>
  );
}

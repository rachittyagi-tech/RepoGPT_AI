
import { useMemo, useState } from "react";

import {
  Clock3,
  MessageSquare,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";

import type { ConversationSummary } from "@/services/chat.service";

interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  isLoading: boolean;
  onNewChat: () => void;
  onSelectConversation: (conversation: ConversationSummary) => void;
  onDeleteConversation: (conversationId: string) => Promise<void>;
}

function isToday(dateString: string) {
  const date = new Date(dateString);
  const now = new Date();

  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  );
}

function isYesterday(dateString: string) {
  const date = new Date(dateString);
  const yesterday = new Date();

  yesterday.setDate(yesterday.getDate() - 1);

  return (
    date.getFullYear() === yesterday.getFullYear() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getDate() === yesterday.getDate()
  );
}

function formatConversationDate(dateString: string) {
  return new Date(dateString).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  isLoading,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
}: ConversationSidebarProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const filteredConversations = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    if (!query) {
      return conversations;
    }

    return conversations.filter((conversation) => {
      const title = conversation.title?.toLowerCase() ?? "";
      const repository = conversation.repository_name.toLowerCase();

      return title.includes(query) || repository.includes(query);
    });
  }, [conversations, searchQuery]);

  const todayConversations = filteredConversations.filter((conversation) =>
    isToday(conversation.updated_at)
  );

  const yesterdayConversations = filteredConversations.filter((conversation) =>
    isYesterday(conversation.updated_at)
  );

  const olderConversations = filteredConversations.filter(
    (conversation) =>
      !isToday(conversation.updated_at) &&
      !isYesterday(conversation.updated_at)
  );

  const handleDelete = async (
    event: React.MouseEvent,
    conversationId: string
  ) => {
    event.stopPropagation();

    if (
      !window.confirm(
        "Delete this conversation? This action cannot be undone."
      )
    ) {
      return;
    }

    setDeletingId(conversationId);

    try {
      await onDeleteConversation(conversationId);
    } catch (error) {
      console.error("Failed to delete conversation:", error);
    } finally {
      setDeletingId(null);
    }
  };

  const renderConversation = (conversation: ConversationSummary) => {
    const isActive = conversation.id === activeConversationId;
    const isDeleting = conversation.id === deletingId;

    const title =
      conversation.title?.trim() || "Repository conversation";

    return (
      <button
        key={conversation.id}
        type="button"
        onClick={() => onSelectConversation(conversation)}
        disabled={isDeleting}
        aria-current={isActive ? "true" : undefined}
        className={[
          "group relative flex w-full items-center gap-3",
          "rounded-lg px-3 py-2.5 text-left",
          "border border-transparent",
          "transition-all duration-150",
          isActive
            ? [
                "border-mint/15",
                "bg-mint/[0.07]",
                "text-foreground",
                "shadow-[inset_2px_0_0_hsl(var(--mint))]",
              ].join(" ")
            : [
                "text-muted",
                "hover:border-border/60",
                "hover:bg-surface-hover/70",
                "hover:text-foreground",
              ].join(" "),
          isDeleting ? "cursor-wait opacity-50" : "",
        ].join(" ")}
      >
        <div
          className={[
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border",
            "transition-colors duration-150",
            isActive
              ? "border-mint/20 bg-mint/[0.08] text-mint"
              : "border-border/60 bg-surface-hover/50 text-muted group-hover:text-foreground",
          ].join(" ")}
        >
          <MessageSquare className="h-3.5 w-3.5" />
        </div>

        <div className="min-w-0 flex-1">
          <p
            className={[
              "truncate text-[13px]",
              isActive ? "font-semibold text-foreground" : "font-medium",
            ].join(" ")}
          >
            {title}
          </p>

          <p className="mt-0.5 truncate font-mono text-[10px] text-muted/75">
            {conversation.repository_name}
          </p>
        </div>

        <div className="flex shrink-0 items-center">
          <span className="text-[9px] text-muted/70 group-hover:hidden">
            {formatConversationDate(conversation.updated_at)}
          </span>

          <span
            role="button"
            tabIndex={0}
            aria-label="Delete conversation"
            onClick={(event) =>
              void handleDelete(event, conversation.id)
            }
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                event.stopPropagation();
                event.currentTarget.click();
              }
            }}
            className={[
              "hidden rounded-md p-1.5",
              "text-muted transition-all duration-150",
              "hover:bg-danger/[0.10] hover:text-danger",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/40",
              "group-hover:block",
            ].join(" ")}
            title="Delete conversation"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </span>
        </div>
      </button>
    );
  };

  return (
    <aside
      className={[
        "flex h-full w-[280px] shrink-0 flex-col",
        "border-r border-border",
        "bg-surface",
      ].join(" ")}
    >
      <div className="flex items-center justify-between border-b border-border/60 px-4 py-3.5">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md border border-mint/20 bg-mint/[0.07]">
            <MessageSquare className="h-3.5 w-3.5 text-mint" />
          </div>

          <div className="min-w-0">
            <p className="text-xs font-semibold text-foreground">
              Conversations
            </p>
            <p className="text-[9px] uppercase tracking-wider text-muted">
              Repository history
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onNewChat}
          aria-label="New chat"
          title="New chat"
          className={[
            "flex h-8 w-8 items-center justify-center rounded-lg",
            "border border-border/70 bg-surface-hover/50",
            "text-muted transition-all duration-150",
            "hover:border-mint/30 hover:bg-mint/[0.07] hover:text-mint",
            "active:scale-[0.97]",
          ].join(" ")}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      <div className="px-3 pt-3">
        <button
          type="button"
          onClick={onNewChat}
          className={[
            "flex w-full items-center justify-center gap-2",
            "rounded-lg border border-border",
            "bg-surface-hover/60",
            "px-3 py-2.5",
            "text-xs font-semibold text-foreground",
            "transition-all duration-150",
            "hover:border-mint/30 hover:bg-mint/[0.06] hover:text-mint",
            "active:scale-[0.99]",
          ].join(" ")}
        >
          <Plus className="h-3.5 w-3.5" />
          New Chat
        </button>
      </div>

      <div className="px-3 pt-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />

          <input
            type="text"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search conversations..."
            aria-label="Search conversations"
            className={[
              "w-full rounded-lg border border-border/80",
              "bg-background/50",
              "py-2.5 pl-9 pr-9",
              "text-xs text-foreground",
              "outline-none",
              "placeholder:text-muted/60",
              "transition-all duration-150",
              "focus:border-mint/40",
              "focus:bg-surface",
              "focus:ring-2 focus:ring-mint/10",
            ].join(" ")}
          />

          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              aria-label="Clear search"
              title="Clear search"
              className="absolute right-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {isLoading ? (
          <div className="space-y-2 px-1 py-2">
            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="h-[58px] animate-pulse rounded-lg border border-border/40 bg-surface-hover/50"
              />
            ))}
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="flex flex-col items-center px-5 py-12 text-center">
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface-hover/60">
              {searchQuery ? (
                <Search className="h-4 w-4 text-muted" />
              ) : (
                <Clock3 className="h-4 w-4 text-muted" />
              )}
            </div>

            <p className="text-xs font-semibold text-foreground">
              {searchQuery
                ? "No conversations found"
                : "No conversations yet"}
            </p>

            <p className="mt-1 max-w-[190px] text-[10px] leading-5 text-muted">
              {searchQuery
                ? "Try a different search term."
                : "Start a new chat to begin exploring your repository."}
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {todayConversations.length > 0 && (
              <section>
                <h3 className="px-3 pb-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">
                  Today
                </h3>

                <div className="space-y-1">
                  {todayConversations.map(renderConversation)}
                </div>
              </section>
            )}

            {yesterdayConversations.length > 0 && (
              <section>
                <h3 className="px-3 pb-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">
                  Yesterday
                </h3>

                <div className="space-y-1">
                  {yesterdayConversations.map(renderConversation)}
                </div>
              </section>
            )}

            {olderConversations.length > 0 && (
              <section>
                <h3 className="px-3 pb-2 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">
                  Older
                </h3>

                <div className="space-y-1">
                  {olderConversations.map(renderConversation)}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}


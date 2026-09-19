
import { useState } from "react";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Check,
  Copy,
  User,
  Sparkles,
  Code2,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { formatDate } from "@/utils/format";

import { SourceCitations } from "./source-citations";
import { TypingIndicator } from "./typing-indicator";

import type { ChatMessage as ChatMessageType } from "@/types/chat.types";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);

      window.setTimeout(() => {
        setCopied(false);
      }, 1500);
    } catch {
      // Clipboard may be unavailable in some browser contexts.
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label={copied ? "Copied to clipboard" : "Copy to clipboard"}
      title={copied ? "Copied" : "Copy"}
      className={cn(
        "inline-flex items-center gap-1.5",
        "rounded-md border border-transparent",
        "px-2 py-1.5",
        "font-mono text-[10px] font-medium",
        "text-muted",
        "transition-all duration-150",
        "hover:border-border",
        "hover:bg-surface-hover",
        "hover:text-foreground",
        "active:scale-[0.98]"
      )}
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-mint" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}

      <span>{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

export function ChatMessage({
  message,
}: {
  message: ChatMessageType;
}) {
  const isUser = message.role === "user";

  return (
    <article
      className={cn(
        "group relative flex gap-3 px-2 py-5 sm:gap-4 sm:px-4",
        "border-b border-border/40 last:border-b-0",
        "transition-colors duration-150",
        isUser
          ? "bg-transparent"
          : "bg-surface/25 hover:bg-surface/40"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center",
          "rounded-lg border shadow-sm",
          isUser
            ? "border-border bg-surface-hover text-muted"
            : [
                "border-amber/25",
                "bg-amber/[0.08]",
                "text-amber",
                "shadow-[0_0_18px_hsl(var(--amber)/0.05)]",
              ].join(" ")
        )}
        aria-hidden="true"
      >
        {isUser ? (
          <User className="h-3.5 w-3.5" />
        ) : (
          <Sparkles className="h-3.5 w-3.5" />
        )}
      </div>

      {/* Message content */}
      <div className="min-w-0 flex-1">
        {/* Header */}
        <div className="mb-2 flex min-h-6 items-center gap-2">
          <span className="text-xs font-semibold tracking-[-0.01em] text-foreground">
            {isUser ? "You" : "RepoGPT AI"}
          </span>

          <span className="text-[10px] text-muted">
            {formatDate(message.timestamp)}
          </span>

          {!isUser && message.streaming && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/20 bg-amber/[0.06] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-amber">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber" />
              Generating
            </span>
          )}

          {!isUser &&
            !message.streaming &&
            message.content && (
              <div className="ml-auto opacity-0 transition-opacity duration-150 group-hover:opacity-100 focus-within:opacity-100">
                <CopyButton text={message.content} />
              </div>
            )}
        </div>

        {/* Streaming / message */}
        {message.streaming && !message.content ? (
          <div className="rounded-lg border border-border/60 bg-surface/35 px-3 py-3">
            <TypingIndicator />
          </div>
        ) : (
          <div
            className={cn(
              "markdown-body max-w-none",
              "text-[13.5px] leading-7",
              "prose prose-sm prose-invert"
            )}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  const codeText = String(children).replace(/\n$/, "");

                  {/* Inline code */}
                  if (!match) {
                    return (
                      <code
                        className={cn(
                          "inline-block max-w-full",
                          "rounded-md border border-border",
                          "bg-surface-hover",
                          "px-1.5 py-0.5",
                          "font-mono text-[12px]",
                          "leading-5 text-foreground"
                        )}
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  }

                  {/* Code block */}
                  return (
                    <div
                      className={cn(
                        "my-4 overflow-hidden",
                        "rounded-xl border border-border",
                        "bg-surface",
                        "shadow-[0_8px_30px_hsl(0_0%_0%/0.12)]"
                      )}
                    >
                      {/* Code header */}
                      <div
                        className={cn(
                          "flex items-center justify-between",
                          "border-b border-border",
                          "bg-surface-hover/70",
                          "px-3 py-2"
                        )}
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          <Code2 className="h-3.5 w-3.5 shrink-0 text-muted" />

                          <span className="truncate font-mono text-[10px] font-medium uppercase tracking-wider text-muted">
                            {match[1]}
                          </span>
                        </div>

                        <CopyButton text={codeText} />
                      </div>

                      {/* Code */}
                      <div className="overflow-x-auto">
                        <SyntaxHighlighter
                          language={match[1]}
                          style={oneDark}
                          customStyle={{
                            margin: 0,
                            padding: "16px",
                            borderRadius: 0,
                            fontSize: "12.5px",
                            lineHeight: "1.65",
                            background: "transparent",
                          }}
                          codeTagProps={{
                            style: {
                              fontFamily:
                                "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                            },
                          }}
                          wrapLongLines={false}
                        >
                          {codeText}
                        </SyntaxHighlighter>
                      </div>
                    </div>
                  );
                },

                pre({ children }) {
                  return <>{children}</>;
                },

                /* Tables */
                table({ children }) {
                  return (
                    <div
                      className={cn(
                        "my-4 overflow-x-auto",
                        "rounded-xl border border-border",
                        "bg-surface/40"
                      )}
                    >
                      <table className="w-full min-w-[520px] border-collapse text-left text-sm">
                        {children}
                      </table>
                    </div>
                  );
                },

                thead({ children }) {
                  return (
                    <thead className="bg-surface-hover">
                      {children}
                    </thead>
                  );
                },

                th({ children }) {
                  return (
                    <th
                      className={cn(
                        "border-b border-border",
                        "px-3 py-2.5",
                        "text-xs font-semibold",
                        "text-foreground"
                      )}
                    >
                      {children}
                    </th>
                  );
                },

                td({ children }) {
                  return (
                    <td
                      className={cn(
                        "border-b border-border/70",
                        "px-3 py-2.5",
                        "text-xs leading-6",
                        "text-muted"
                      )}
                    >
                      {children}
                    </td>
                  );
                },

                /* Links */
                a({ children, href, ...props }) {
                  return (
                    <a
                      {...props}
                      href={href}
                      target="_blank"
                      rel="noreferrer"
                      className={cn(
                        "font-medium text-mint",
                        "underline-offset-4",
                        "transition-colors duration-150",
                        "hover:text-mint hover:underline"
                      )}
                    >
                      {children}
                    </a>
                  );
                },

                /* Blockquotes */
                blockquote({ children }) {
                  return (
                    <blockquote
                      className={cn(
                        "my-4 rounded-r-lg",
                        "border-l-2 border-mint/40",
                        "bg-surface/50",
                        "px-4 py-3 text-muted"
                      )}
                    >
                      {children}
                    </blockquote>
                  );
                },

                /* Horizontal rule */
                hr() {
                  return (
                    <hr className="my-6 border-0 border-t border-border" />
                  );
                },

                /* Images */
                img({ src, alt, ...props }) {
                  return (
                    <img
                      {...props}
                      src={src}
                      alt={alt || ""}
                      loading="lazy"
                      className={cn(
                        "my-4 max-w-full",
                        "rounded-xl border border-border",
                        "shadow-sm"
                      )}
                    />
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Sources */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-4">
            <SourceCitations sources={message.sources} />
          </div>
        )}
      </div>
    </article>
  );
}


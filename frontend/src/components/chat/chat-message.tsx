import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Check, Copy, User, Sparkles } from "lucide-react";
import { cn } from "@/utils/cn";
import { formatDate } from "@/utils/format";
import { SourceCitations } from "./source-citations";
import { TypingIndicator } from "./typing-indicator";
import type { ChatMessage as ChatMessageType } from "@/types/chat.types";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <button
      onClick={handleCopy}
      aria-label="Copy to clipboard"
      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted hover:bg-surface-hover hover:text-foreground"
    >
      {copied ? <Check className="h-3 w-3 text-mint" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

/**
 * Renders one chat turn as a "diff comment" — a left-border-accented block
 * rather than a rounded bubble — mint for the user (like a diff addition),
 * amber for the AI (like an inline review annotation). This is the
 * product's signature chat styling, tying visually back to the code/diff
 * subject matter instead of a generic chat-bubble template.
 */
export function ChatMessage({ message }: { message: ChatMessageType }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "animate-fade-in border-l-2 py-2 pl-4 pr-2",
        isUser ? "border-l-mint" : "border-l-amber"
      )}
    >
      <div className="mb-1 flex items-center gap-2 font-mono text-[11px] text-muted">
        {isUser ? <User className="h-3 w-3" /> : <Sparkles className="h-3 w-3" />}
        <span className="font-medium text-foreground">{isUser ? "You" : "RepoGPT AI"}</span>
        <span>{formatDate(message.timestamp)}</span>
        {!isUser && !message.streaming && message.content && <CopyButton text={message.content} />}
      </div>

      {message.streaming && !message.content ? (
        <TypingIndicator />
      ) : (
        <div className="markdown-body prose prose-sm max-w-none prose-invert text-[13.5px] leading-relaxed">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                const codeText = String(children).replace(/\n$/, "");

                if (!match) {
                  return (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                }

                return (
                  <div className="relative my-2">
                    <div className="flex items-center justify-between rounded-t-md border border-b-0 border-border bg-surface-hover px-3 py-1">
                      <span className="font-mono text-[11px] text-muted">{match[1]}</span>
                      <CopyButton text={codeText} />
                    </div>
                    <SyntaxHighlighter
                      language={match[1]}
                      style={oneDark}
                      customStyle={{
                        margin: 0,
                        borderRadius: "0 0 6px 6px",
                        fontSize: "12.5px",
                        border: "1px solid hsl(var(--border))",
                        borderTop: "none",
                      }}
                    >
                      {codeText}
                    </SyntaxHighlighter>
                  </div>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      )}

      {message.sources && message.sources.length > 0 && <SourceCitations sources={message.sources} />}
    </div>
  );
}

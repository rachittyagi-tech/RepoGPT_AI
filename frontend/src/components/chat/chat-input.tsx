
import { useRef, useState, type KeyboardEvent } from "react";
import { Send, Square, Sparkles } from "lucide-react";

import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

export function ChatInput({
  onSend,
  onStop,
  isStreaming,
  disabled = false,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmedValue = value.trim();

    if (!trimmedValue || isStreaming || disabled) {
      return;
    }

    onSend(trimmedValue);
    setValue("");

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (
    e: KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const element = textareaRef.current;

    if (!element) {
      return;
    }

    element.style.height = "auto";
    element.style.height = `${Math.min(
      element.scrollHeight,
      160
    )}px`;
  };

  const hasText = value.trim().length > 0;

  return (
    <div className="px-2 pb-3 pt-2 sm:px-4 sm:pb-4">
      <div
        className={[
          "relative overflow-hidden rounded-xl",
          "border border-border",
          "bg-surface",
          "shadow-[0_8px_30px_hsl(0_0%_0%/0.12)]",
          "transition-all duration-150",
          "focus-within:border-mint/40",
          "focus-within:shadow-[0_8px_30px_hsl(0_0%_0%/0.16)]",
        ].join(" ")}
      >
        <div className="flex items-end gap-2 p-2">
          <div className="flex min-w-0 flex-1 items-end">
            <Textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                handleInput();
              }}
              onKeyDown={handleKeyDown}
              placeholder={
                disabled
                  ? "Select a repository to start chatting…"
                  : "Ask about this repository…"
              }
              disabled={disabled}
              rows={1}
              aria-label="Chat message"
              className={[
                "min-h-[42px] max-h-40 resize-none",
                "border-0 bg-transparent",
                "px-2.5 py-2.5",
                "font-sans text-sm leading-6",
                "shadow-none",
                "placeholder:text-muted/70",
                "focus-visible:outline-none",
                "focus-visible:ring-0",
                "disabled:cursor-not-allowed",
                "disabled:opacity-60",
              ].join(" ")}
            />
          </div>

          {isStreaming ? (
            <Button
              type="button"
              variant="destructive"
              size="icon"
              onClick={onStop}
              aria-label="Stop generating"
              title="Stop generating"
              className={[
                "h-9 w-9 shrink-0 rounded-lg",
                "shadow-sm",
                "transition-all duration-150",
                "hover:scale-[1.02]",
                "active:scale-[0.98]",
              ].join(" ")}
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </Button>
          ) : (
            <Button
              type="button"
              size="icon"
              onClick={handleSend}
              disabled={disabled || !hasText}
              aria-label="Send message"
              title="Send message"
              className={[
                "h-9 w-9 shrink-0 rounded-lg",
                "transition-all duration-150",
                "hover:scale-[1.02]",
                "active:scale-[0.98]",
                "disabled:scale-100",
              ].join(" ")}
            >
              <Send className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border/60 px-3 py-1.5">
          <div className="flex min-w-0 items-center gap-1.5 text-[10px] text-muted">
            <Sparkles className="h-3 w-3 shrink-0 text-amber" />

            <span className="truncate">
              {isStreaming
                ? "RepoGPT AI is generating a response…"
                : "Ask about architecture, code, APIs, or functions"}
            </span>
          </div>

          <span className="hidden shrink-0 font-mono text-[9px] text-muted/70 sm:inline">
            Enter ↵
          </span>
        </div>
      </div>

      <p className="mt-2 text-center text-[10px] text-muted/60">
        Shift + Enter for a new line
      </p>
    </div>
  );
}



import { ChevronDown, FolderGit2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";

import { useRepositories } from "@/hooks/use-repositories";

import { displayRepoName } from "@/utils/format";

interface ChatHeaderProps {
  activeRepository: string | null;
  onRepositoryChange: (repositoryName: string) => void;
  onClearChat: () => void;
  hasMessages: boolean;
}

export function ChatHeader({
  activeRepository,
  onRepositoryChange,
  onClearChat,
  hasMessages,
}: ChatHeaderProps) {
  const { data: repositories } = useRepositories();

  return (
    <header className="flex min-h-[58px] items-center justify-between gap-3 border-b border-border bg-surface/95 px-3 backdrop-blur-sm sm:px-4">
      <div className="flex min-w-0 items-center gap-2.5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-mint/20 bg-mint/[0.07]">
          <FolderGit2
            className="h-4 w-4 text-mint"
            aria-hidden="true"
          />
        </div>

        <div className="min-w-0">
          <p className="hidden text-[9px] font-semibold uppercase tracking-[0.12em] text-muted sm:block">
            Repository
          </p>

          <div className="relative mt-0 sm:mt-0.5">
            <select
              value={activeRepository ?? ""}
              onChange={(event) =>
                onRepositoryChange(event.target.value)
              }
              aria-label="Select repository to chat with"
              className={[
                "max-w-[190px] appearance-none",
                "cursor-pointer rounded-md",
                "border border-transparent",
                "bg-transparent",
                "py-1 pr-7",
                "font-mono text-xs font-medium",
                "text-foreground",
                "outline-none",
                "transition-all duration-150",
                "hover:border-border hover:bg-surface-hover/60",
                "focus:border-mint/30",
                "focus:bg-surface-hover/60",
                "focus:ring-2 focus:ring-mint/10",
                "sm:max-w-xs",
              ].join(" ")}
            >
              <option value="" disabled>
                Select a repository…
              </option>

              {repositories?.map((repo) => (
                <option
                  key={repo.repository_name}
                  value={repo.repository_name}
                >
                  {displayRepoName(repo.repository_name)}
                </option>
              ))}
            </select>

            <ChevronDown
              className="pointer-events-none absolute right-1 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted"
              aria-hidden="true"
            />
          </div>
        </div>
      </div>

      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={onClearChat}
        disabled={!hasMessages}
        title="Clear current chat"
        aria-label="Clear current chat"
        className={[
          "shrink-0 gap-1.5",
          "border border-transparent",
          "text-muted",
          "transition-all duration-150",
          "hover:border-danger/20",
          "hover:bg-danger/[0.07]",
          "hover:text-danger",
          "disabled:cursor-not-allowed",
          "disabled:opacity-40",
        ].join(" ")}
      >
        <Trash2 className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Clear chat</span>
      </Button>
    </header>
  );
}


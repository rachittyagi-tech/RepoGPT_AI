import { Trash2, FolderGit2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRepositories } from "@/hooks/use-repositories";
import { displayRepoName } from "@/utils/format";

interface ChatHeaderProps {
  activeRepository: string | null;
  onRepositoryChange: (repositoryName: string) => void;
  onClearChat: () => void;
  hasMessages: boolean;
}

/** "Repository Switching" + "Conversation Reset" chat features. */
export function ChatHeader({
  activeRepository,
  onRepositoryChange,
  onClearChat,
  hasMessages,
}: ChatHeaderProps) {
  const { data: repositories } = useRepositories();

  return (
    <div className="flex items-center justify-between gap-2 border-b border-border bg-surface px-4 py-2.5">
      <div className="flex min-w-0 items-center gap-2">
        <FolderGit2 className="h-4 w-4 shrink-0 text-mint" aria-hidden="true" />
        <select
          value={activeRepository ?? ""}
          onChange={(e) => onRepositoryChange(e.target.value)}
          aria-label="Select repository to chat with"
          className="max-w-[220px] truncate rounded border border-border bg-surface px-2 py-1 font-mono text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint sm:max-w-xs"
        >
          <option value="" disabled>
            Select a repository…
          </option>
          {repositories?.map((repo) => (
            <option key={repo.repository_name} value={repo.repository_name}>
              {displayRepoName(repo.repository_name)}
            </option>
          ))}
        </select>
      </div>

      <Button variant="ghost" size="sm" onClick={onClearChat} disabled={!hasMessages}>
        <Trash2 className="h-3.5 w-3.5" />
        Clear chat
      </Button>
    </div>
  );
}

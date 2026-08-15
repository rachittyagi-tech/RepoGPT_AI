import { Moon, Sun, FolderGit2 } from "lucide-react";
import { Breadcrumbs } from "./breadcrumbs";
import { useTheme } from "@/hooks/use-theme";
import { useRepositoryContext } from "@/contexts/repository-context";
import { Badge } from "@/components/ui/badge";
import { displayRepoName } from "@/utils/format";

export function TopNav() {
  const { theme, toggleTheme } = useTheme();
  const { activeRepository } = useRepositoryContext();

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-4 md:px-6">
      <Breadcrumbs />

      <div className="flex items-center gap-3">
        {activeRepository && (
          <Badge variant="mint" className="hidden sm:inline-flex">
            <FolderGit2 className="h-3 w-3" aria-hidden="true" />
            {displayRepoName(activeRepository)}
          </Badge>
        )}

        <button
          onClick={toggleTheme}
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="flex h-8 w-8 items-center justify-center rounded border border-border text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </header>
  );
}

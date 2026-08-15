import { Link } from "react-router-dom";
import { TerminalSquare } from "lucide-react";
import { cn } from "@/utils/cn";

export default function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
      <TerminalSquare className="h-10 w-10 text-muted" aria-hidden="true" />
      <div>
        <p className="font-mono text-sm text-muted">404</p>
        <h1 className="mt-1 text-lg font-semibold">Page not found</h1>
        <p className="mt-1 max-w-xs text-sm text-muted">
          This route doesn't exist — like a file that was never in the repo.
        </p>
      </div>
      <Link
        to="/"
        className={cn(
          "inline-flex h-9 items-center justify-center rounded bg-mint px-4 text-sm font-medium text-mint-foreground hover:opacity-90"
        )}
      >
        Back to Dashboard
      </Link>
    </div>
  );
}

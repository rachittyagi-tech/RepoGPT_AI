import { Link, useLocation } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";

const LABELS: Record<string, string> = {
  repository: "Repository",
  chat: "Chat",
  explorer: "Explorer",
  settings: "Settings",
};

/** Auto-derives crumbs from the current URL path — no per-page wiring needed. */
export function Breadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);

  if (segments.length === 0) {
    return (
      <div className="flex items-center gap-1.5 font-mono text-xs text-muted">
        <Home className="h-3.5 w-3.5" aria-hidden="true" />
        <span className="text-foreground">dashboard</span>
      </div>
    );
  }

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 font-mono text-xs text-muted">
      <Link to="/" className="flex items-center hover:text-foreground">
        <Home className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>
      {segments.map((segment, index) => {
        const path = "/" + segments.slice(0, index + 1).join("/");
        const isLast = index === segments.length - 1;
        const label = LABELS[segment] ?? decodeURIComponent(segment);
        return (
          <span key={path} className="flex items-center gap-1.5">
            <ChevronRight className="h-3 w-3" aria-hidden="true" />
            {isLast ? (
              <span className="text-foreground" aria-current="page">
                {label}
              </span>
            ) : (
              <Link to={path} className="hover:text-foreground">
                {label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}

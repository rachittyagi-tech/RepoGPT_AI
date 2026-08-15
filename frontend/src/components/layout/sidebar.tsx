import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderGit2,
  MessageSquare,
  FolderTree,
  BarChart3,
  Settings,
  Terminal,
} from "lucide-react";
import { cn } from "@/utils/cn";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/repository", label: "Repository", icon: FolderGit2 },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/explorer", label: "Explorer", icon: FolderTree },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="hidden w-56 shrink-0 flex-col border-r border-border bg-surface md:flex">
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <Terminal className="h-5 w-5 text-mint" aria-hidden="true" />
        <span className="font-mono text-sm font-semibold tracking-tight">RepoGPT AI</span>
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-2" aria-label="Primary">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-mint/10 text-mint font-medium"
                  : "text-muted hover:bg-surface-hover hover:text-foreground"
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-3 font-mono text-[11px] text-muted">
        v1.0.0 · Step 12
      </div>
    </aside>
  );
}

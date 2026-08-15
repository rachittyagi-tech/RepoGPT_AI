import { NavLink } from "react-router-dom";
import { LayoutDashboard, FolderGit2, MessageSquare, FolderTree, BarChart3, Settings } from "lucide-react";
import { cn } from "@/utils/cn";

const NAV_ITEMS = [
  { to: "/", label: "Home", icon: LayoutDashboard, end: true },
  { to: "/repository", label: "Repo", icon: FolderGit2 },
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/explorer", label: "Files", icon: FolderTree },
  { to: "/analytics", label: "Stats", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: Settings },
];

/** Bottom tab bar shown only below the `md` breakpoint, mirroring the desktop Sidebar's items. */
export function MobileNav() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border bg-surface md:hidden"
      aria-label="Primary"
    >
      {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] transition-colors",
              isActive ? "text-mint" : "text-muted"
            )
          }
        >
          <Icon className="h-5 w-5" aria-hidden="true" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

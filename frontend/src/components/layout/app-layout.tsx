import { Suspense, type ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { TopNav } from "./topnav";
import { Footer } from "./footer";
import { MobileNav } from "./mobile-nav";
import { ErrorBoundary } from "./error-boundary";
import { Skeleton } from "@/components/ui/skeleton";

function PageFallback() {
  return (
    <div className="flex flex-col gap-4 p-6">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

export function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-bg text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopNav />
        <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
          <ErrorBoundary>
            <Suspense fallback={<PageFallback />}>{children}</Suspense>
          </ErrorBoundary>
        </main>
        <Footer />
      </div>
      <MobileNav />
    </div>
  );
}

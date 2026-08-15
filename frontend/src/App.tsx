import { lazy } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/contexts/theme-context";
import { RepositoryProvider } from "@/contexts/repository-context";
import { ToastProvider } from "@/contexts/toast-context";
import { Toaster } from "@/components/ui/toaster";
import { AppLayout } from "@/components/layout/app-layout";
import { ErrorBoundary } from "@/components/layout/error-boundary";

// Code splitting: each page is its own chunk, only fetched when visited.
const DashboardPage = lazy(() => import("@/pages/dashboard-page"));
const RepositoryPage = lazy(() => import("@/pages/repository-page"));
const ChatPage = lazy(() => import("@/pages/chat-page"));
const ExplorerPage = lazy(() => import("@/pages/explorer-page"));
const AnalyticsPage = lazy(() => import("@/pages/analytics-page"));
const SettingsPage = lazy(() => import("@/pages/settings-page"));
const NotFoundPage = lazy(() => import("@/pages/not-found-page"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <RepositoryProvider>
            <ToastProvider>
              <BrowserRouter>
                <AppLayout>
                  <Routes>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/repository" element={<RepositoryPage />} />
                    <Route path="/chat" element={<ChatPage />} />
                    <Route path="/explorer" element={<ExplorerPage />} />
                    <Route path="/analytics" element={<AnalyticsPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="*" element={<NotFoundPage />} />
                  </Routes>
                </AppLayout>
              </BrowserRouter>
              <Toaster />
            </ToastProvider>
          </RepositoryProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

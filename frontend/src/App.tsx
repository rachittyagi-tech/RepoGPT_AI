import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ThemeProvider } from "@/contexts/theme-context";
import { RepositoryProvider } from "@/contexts/repository-context";
import { ToastProvider } from "@/contexts/toast-context";
import { AuthProvider } from "@/contexts/auth-context";

import { Toaster } from "@/components/ui/toaster";
import { AppLayout } from "@/components/layout/app-layout";
import { ErrorBoundary } from "@/components/layout/error-boundary";
import { ProtectedRoute } from "@/components/layout/protected-route";

const AuthPage = lazy(() => import("@/pages/login-page"));

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

function PageLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-sm text-muted-foreground">
        Loading RepoGPT AI...
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <AuthProvider>
            <RepositoryProvider>
              <ToastProvider>
                <BrowserRouter>
                  <Suspense fallback={<PageLoader />}>
                    <Routes>

                      {/* Authentication */}
                      <Route
                        path="/"
                        element={<AuthPage />}
                      />

                      {/* Protected application */}
                      <Route element={<ProtectedRoute />}>

                        <Route
                          path="/dashboard"
                          element={
                            <AppLayout>
                              <DashboardPage />
                            </AppLayout>
                          }
                        />

                        <Route
                          path="/repository"
                          element={
                            <AppLayout>
                              <RepositoryPage />
                            </AppLayout>
                          }
                        />

                        <Route
                          path="/chat"
                          element={
                            <AppLayout>
                              <ChatPage />
                            </AppLayout>
                          }
                        />

                        <Route
                          path="/explorer"
                          element={
                            <AppLayout>
                              <ExplorerPage />
                            </AppLayout>
                          }
                        />

                        <Route
                          path="/analytics"
                          element={
                            <AppLayout>
                              <AnalyticsPage />
                            </AppLayout>
                          }
                        />

                        <Route
                          path="/settings"
                          element={
                            <AppLayout>
                              <SettingsPage />
                            </AppLayout>
                          }
                        />

                      </Route>

                      {/* 404 */}
                      <Route
                        path="*"
                        element={<NotFoundPage />}
                      />

                    </Routes>
                  </Suspense>

                  <Toaster />
                </BrowserRouter>
              </ToastProvider>
            </RepositoryProvider>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
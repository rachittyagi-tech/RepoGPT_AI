import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { LOCAL_STORAGE_KEYS } from "@/utils/constants";

interface RepositoryContextValue {
  activeRepository: string | null;
  setActiveRepository: (repositoryName: string | null) => void;
}

const RepositoryContext = createContext<RepositoryContextValue | undefined>(undefined);

/**
 * Tracks which repository is "active" across the whole app — set from the
 * Dashboard or Repository page, read by the Chat and Explorer pages so
 * navigating between them doesn't lose context. Persisted to
 * localStorage so a page refresh doesn't reset it.
 */
export function RepositoryProvider({ children }: { children: ReactNode }) {
  const [activeRepository, setActiveRepositoryState] = useState<string | null>(() =>
    typeof window === "undefined" ? null : window.localStorage.getItem(LOCAL_STORAGE_KEYS.activeRepository)
  );

  useEffect(() => {
    if (activeRepository) {
      window.localStorage.setItem(LOCAL_STORAGE_KEYS.activeRepository, activeRepository);
    } else {
      window.localStorage.removeItem(LOCAL_STORAGE_KEYS.activeRepository);
    }
  }, [activeRepository]);

  return (
    <RepositoryContext.Provider
      value={{ activeRepository, setActiveRepository: setActiveRepositoryState }}
    >
      {children}
    </RepositoryContext.Provider>
  );
}

export function useRepositoryContext(): RepositoryContextValue {
  const ctx = useContext(RepositoryContext);
  if (!ctx) throw new Error("useRepositoryContext must be used within a RepositoryProvider.");
  return ctx;
}

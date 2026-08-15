import { useToastContext } from "@/contexts/toast-context";

/** Convenience hook: `const { success, error } = useToast()`. */
export function useToast() {
  const { showToast, toasts, dismissToast } = useToastContext();

  return {
    toasts,
    dismissToast,
    success: (title: string, description?: string) => showToast({ title, description, variant: "success" }),
    error: (title: string, description?: string) => showToast({ title, description, variant: "error" }),
    info: (title: string, description?: string) => showToast({ title, description, variant: "default" }),
  };
}

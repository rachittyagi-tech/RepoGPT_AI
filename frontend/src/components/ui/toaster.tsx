import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, X, XCircle, Info } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/utils/cn";
import type { ToastVariant } from "@/contexts/toast-context";

const ICONS: Record<ToastVariant, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  default: Info,
};

const ACCENTS: Record<ToastVariant, string> = {
  success: "border-l-mint",
  error: "border-l-danger",
  default: "border-l-amber",
};

export function Toaster() {
  const { toasts, dismissToast } = useToast();

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
      aria-live="polite"
      aria-atomic="true"
    >
      <AnimatePresence>
        {toasts.map((toast) => {
          const Icon = ICONS[toast.variant];
          return (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24 }}
              transition={{ duration: 0.18 }}
              role="status"
              className={cn(
                "flex items-start gap-3 rounded-md border border-border border-l-4 bg-surface p-3 shadow-lg",
                ACCENTS[toast.variant]
              )}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground">{toast.title}</p>
                {toast.description && (
                  <p className="mt-0.5 truncate text-xs text-muted">{toast.description}</p>
                )}
              </div>
              <button
                onClick={() => dismissToast(toast.id)}
                aria-label="Dismiss notification"
                className="text-muted hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}

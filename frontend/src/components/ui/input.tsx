import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded border border-border bg-surface px-3 py-1 text-sm text-foreground placeholder:text-muted transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mint focus-visible:ring-offset-0",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";

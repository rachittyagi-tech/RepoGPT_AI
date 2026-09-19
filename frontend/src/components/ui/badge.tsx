import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/utils/cn";

const badgeVariants = cva(
  [
    "inline-flex items-center gap-1.5",
    "min-h-6 max-w-full",
    "rounded-md border",
    "px-2.5 py-1",
    "font-mono text-[11px] font-medium leading-none",
    "whitespace-nowrap",
    "transition-all duration-150",
    "select-none",
    "focus-visible:outline-none",
    "focus-visible:ring-2 focus-visible:ring-mint/40",
    "focus-visible:ring-offset-1 focus-visible:ring-offset-background",
  ].join(" "),
  {
    variants: {
      variant: {
        default: [
          "border-border/80",
          "bg-surface-hover/80",
          "text-foreground",
          "hover:border-border",
          "hover:bg-surface-hover",
        ].join(" "),

        mint: [
          "border-mint/25",
          "bg-mint/[0.08]",
          "text-mint",
          "hover:border-mint/40",
          "hover:bg-mint/[0.12]",
        ].join(" "),

        amber: [
          "border-amber/25",
          "bg-amber/[0.08]",
          "text-amber",
          "hover:border-amber/40",
          "hover:bg-amber/[0.12]",
        ].join(" "),

        danger: [
          "border-danger/25",
          "bg-danger/[0.08]",
          "text-danger",
          "hover:border-danger/40",
          "hover:bg-danger/[0.12]",
        ].join(" "),

        outline: [
          "border-border/80",
          "bg-transparent",
          "text-muted",
          "hover:border-border",
          "hover:bg-surface-hover/50",
          "hover:text-foreground",
        ].join(" "),
      },
    },

    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({
  className,
  variant,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        badgeVariants({ variant }),
        className
      )}
      {...props}
    />
  );
}

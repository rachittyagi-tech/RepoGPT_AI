import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/utils/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-[11px] font-mono font-medium",
  {
    variants: {
      variant: {
        default: "bg-surface-hover text-foreground border border-border",
        mint: "bg-mint/15 text-mint border border-mint/30",
        amber: "bg-amber/15 text-amber border border-amber/30",
        danger: "bg-danger/15 text-danger border border-danger/30",
        outline: "border border-border text-muted",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

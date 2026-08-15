import type { HTMLAttributes } from "react";
import { cn } from "@/utils/cn";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded bg-surface-hover", className)}
      role="status"
      aria-label="Loading"
      {...props}
    />
  );
}

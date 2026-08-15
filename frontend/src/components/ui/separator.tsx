import { cn } from "@/utils/cn";

export function Separator({
  orientation = "horizontal",
  className,
}: {
  orientation?: "horizontal" | "vertical";
  className?: string;
}) {
  return (
    <div
      role="separator"
      className={cn(
        "bg-border",
        orientation === "horizontal" ? "h-px w-full" : "w-px h-full",
        className
      )}
    />
  );
}

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Button, type ButtonProps } from "@/components/ui/button";

export type EmptyStateProps = {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  actionProps?: Omit<ButtonProps, "children" | "onClick">;
  icon?: ReactNode;
  className?: string;
};

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
  actionProps,
  icon,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-start rounded-xl border border-dashed border-line bg-paper px-6 py-10",
        className,
      )}
    >
      {icon ? <div className="mb-4 text-muted">{icon}</div> : null}
      <h3
        className="text-xl font-medium tracking-[-0.02em] text-ink"
        style={{ fontFamily: "var(--font-family-display)" }}
      >
        {title}
      </h3>
      {description ? (
        <p className="mt-2 max-w-[40ch] text-sm leading-relaxed text-muted">
          {description}
        </p>
      ) : null}
      {actionLabel && onAction ? (
        <Button className="mt-6" onClick={onAction} {...actionProps}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

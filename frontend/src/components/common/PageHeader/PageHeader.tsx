import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type PageHeaderProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
};

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="max-w-[52ch]">
        {eyebrow ? (
          <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-muted">
            {eyebrow}
          </p>
        ) : null}
        <h1
          className="text-[clamp(1.75rem,3vw,2.5rem)] font-medium leading-[1.1] tracking-[-0.02em] text-ink"
          style={{ fontFamily: "var(--font-family-display)" }}
        >
          {title}
        </h1>
        {description ? (
          <p className="mt-2 text-sm leading-relaxed text-muted md:text-base">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

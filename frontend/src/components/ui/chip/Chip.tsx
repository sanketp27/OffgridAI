import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export type ChipTone = "neutral" | "signal" | "amber" | "coral" | "violet";

export type ChipProps = HTMLAttributes<HTMLSpanElement> & {
  tone?: ChipTone;
  children: ReactNode;
};

const toneClass: Record<ChipTone, string> = {
  neutral: "bg-chalk text-ink border-line",
  signal: "bg-signal-soft text-ink border-signal/20",
  amber: "bg-amber-soft text-ink border-amber/25",
  coral: "bg-coral-soft text-coral border-coral/20",
  violet: "bg-violet-signal-soft text-violet-signal border-violet-signal/20",
};

export function Chip({
  tone = "neutral",
  className,
  children,
  ...props
}: ChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[12px] font-semibold",
        toneClass[tone],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

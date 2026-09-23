"use client";

import { Chip } from "@/components/ui";
import { formatInr } from "@/lib/format";
import type { Insight } from "@/lib/api";
import { cn } from "@/lib/cn";

function borderForSignal(signal: string) {
  if (signal.includes("fit")) return "border-l-amber";
  if (signal.includes("stock")) return "border-l-coral";
  if (signal.includes("unmet") || signal.includes("demand"))
    return "border-l-signal";
  return "border-l-violet-signal";
}

type InsightCardProps = {
  insight: Insight;
  index: number;
};

export function InsightCard({ insight, index }: InsightCardProps) {
  const signal = String(insight.signal_type);

  return (
    <article
      className={cn(
        "relative rounded-[20px] border border-line bg-paper p-5 shadow-elev-1 border-l-4 md:p-6",
        borderForSignal(signal),
      )}
      style={{
        animation: `resultIn var(--motion-insight-duration) var(--ease-out) both`,
        animationDelay: `calc(${index} * var(--motion-insight-stagger))`,
      }}
    >
      {insight.urgency_days != null && insight.urgency_days <= 5 ? (
        <span
          className="absolute right-0 top-0 h-full w-1 rounded-r-[20px] bg-coral/70"
          aria-hidden
          title={`Act within ${insight.urgency_days} days`}
        />
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Chip tone="coral">
          {formatInr(insight.est_revenue_at_risk)} at risk
        </Chip>
        {insight.trend_pct != null ? (
          <Chip>↑ {insight.trend_pct}%</Chip>
        ) : (
          <Chip tone="amber">New</Chip>
        )}
      </div>

      <h3 className="font-display mt-4 text-xl text-ink md:text-[1.35rem]">
        {insight.label}
      </h3>
      <p className="mt-2 max-w-[58ch] text-sm leading-relaxed text-muted md:text-[15px]">
        {insight.brief}
      </p>
      <p className="mt-4 text-sm font-semibold text-ink">
        {insight.recommended_action}
      </p>
      <p className="mt-2 text-[11px] uppercase tracking-[0.1em] text-muted">
        {signal.replaceAll("_", " ")} · {insight.occurrences} events ·{" "}
        {insight.unique_shoppers} shoppers
        {insight.urgency_days != null
          ? ` · within ${insight.urgency_days}d`
          : ""}
      </p>
    </article>
  );
}

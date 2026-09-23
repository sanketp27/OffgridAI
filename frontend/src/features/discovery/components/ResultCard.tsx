"use client";

import { Button, Chip } from "@/components/ui";
import { ProductImage } from "@/components/common/ProductImage";
import { formatInr } from "@/lib/format";
import type { SearchResult } from "@/lib/api";
import { cn } from "@/lib/cn";

type ResultCardProps = {
  result: SearchResult;
  index: number;
  selected?: boolean;
  onChoose: (result: SearchResult) => void;
};

export function ResultCard({
  result,
  index,
  selected,
  onChoose,
}: ResultCardProps) {
  const isExact = result.match_quality === "exact";
  const tone =
    result.match_quality === "exact"
      ? "signal"
      : result.match_quality === "near"
        ? "amber"
        : "coral";

  return (
    <article
      className={cn(
        "flex flex-col overflow-hidden rounded-[20px] border bg-paper shadow-elev-1 transition-[box-shadow,transform,border-color]",
        "duration-[var(--duration-base)] ease-[var(--ease-out)]",
        selected
          ? "border-signal shadow-elev-2 ring-2 ring-signal/20"
          : isExact
            ? "border-line"
            : "border-amber/35",
      )}
      style={{
        animation: `resultIn var(--motion-results-duration) var(--ease-out) both`,
        animationDelay: `calc(${index} * var(--motion-results-stagger))`,
      }}
    >
      <div className="relative aspect-[4/3] bg-chalk">
        <ProductImage
          src={result.image_url}
          alt={result.name}
          sizes="(max-width: 768px) 100vw, 33vw"
        />
        <div className="absolute left-3 top-3">
          <Chip tone={tone}>
            {result.match_quality} · {Math.round(result.match_score * 100)}%
          </Chip>
        </div>
      </div>

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-[15px] font-semibold leading-snug text-ink md:text-base">
            {result.name}
          </h3>
          <p className="shrink-0 text-sm font-semibold tabular-nums text-ink">
            {formatInr(result.price, result.currency)}
          </p>
        </div>
        <p className="mt-3 max-w-[42ch] flex-1 text-sm leading-relaxed text-muted">
          {result.match_explanation}
        </p>
        <p className="mt-3 text-[11px] font-medium uppercase tracking-[0.1em] text-muted">
          Grounded · SKU {result.sku_id}
        </p>
        <Button
          className="mt-5 w-full"
          variant={selected ? "secondary" : "primary"}
          onClick={() => onChoose(result)}
        >
          {selected ? "Selected" : "Choose"}
        </Button>
      </div>
    </article>
  );
}

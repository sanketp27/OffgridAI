"use client";

import { Button, Chip } from "@/components/ui";
import { ProductImage } from "@/components/common/ProductImage";
import type { RescueOption, StockoutRescue } from "@/lib/api";
import { formatInr } from "@/lib/format";
import { cn } from "@/lib/cn";

type StockoutRescuePanelProps = {
  rescue: StockoutRescue;
  onAccept: (option: RescueOption) => void;
  acceptedId?: string | null;
};

export function StockoutRescuePanel({
  rescue,
  onAccept,
  acceptedId,
}: StockoutRescuePanelProps) {
  if (!rescue.triggered) return null;

  return (
    <section
      className="mb-8 overflow-hidden rounded-[20px] border border-coral/25 bg-paper shadow-elev-1"
      style={{
        animation: `fitCheckIn var(--motion-fitcheck-duration) var(--ease-out) both`,
      }}
    >
      <div className="flex flex-col gap-3 border-b border-coral/15 bg-coral-soft/80 px-5 py-5 md:flex-row md:items-center md:justify-between md:px-6">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone="coral">Stockout rescue</Chip>
            <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink/60">
              Revenue recovered path
            </span>
          </div>
          <h3 className="font-display mt-2 text-xl text-ink md:text-2xl">
            {rescue.preferred_name}
            <span className="text-muted"> · wanted</span>
          </h3>
          <p className="mt-1 max-w-[52ch] text-sm text-ink/75">{rescue.reason}</p>
        </div>
        <div className="opacity-45 grayscale">
          <div className="relative h-20 w-28 overflow-hidden rounded-xl border border-line bg-chalk">
            <ProductImage
              src={
                rescue.options.find((o) => o.sku_id === rescue.preferred_sku_id)
                  ?.image_url ||
                rescue.options[0]?.image_url ||
                "/products/rn-210.svg"
              }
              alt=""
              sizes="112px"
            />
          </div>
        </div>
      </div>

      <div className="grid gap-3 p-4 md:grid-cols-3 md:gap-4 md:p-5">
        {rescue.options.map((option) => {
          const selected = acceptedId === option.option_id;
          return (
            <article
              key={option.option_id}
              className={cn(
                "flex flex-col rounded-2xl border bg-chalk/40 p-4",
                selected ? "border-signal ring-2 ring-signal/20" : "border-line",
              )}
            >
              {option.image_url ? (
                <div className="relative mb-3 aspect-[4/3] overflow-hidden rounded-xl bg-paper">
                  <ProductImage
                    src={option.image_url}
                    alt=""
                    sizes="200px"
                  />
                </div>
              ) : null}
              <Chip tone="neutral" className="self-start capitalize">
                {option.type.replaceAll("_", " ")}
              </Chip>
              <h4 className="mt-2 text-sm font-semibold text-ink">{option.name}</h4>
              {option.price != null ? (
                <p className="mt-1 text-sm tabular-nums text-muted">
                  {formatInr(option.price, option.currency ?? "INR")}
                </p>
              ) : null}
              <p className="mt-3 flex-1 text-[13px] font-medium leading-relaxed text-ink/80">
                {option.tradeoff}
              </p>
              <Button
                className="mt-4 w-full"
                size="sm"
                variant={selected ? "secondary" : "primary"}
                onClick={() => onAccept(option)}
              >
                {selected ? "Accepted" : "Accept"}
              </Button>
            </article>
          );
        })}
      </div>
    </section>
  );
}

"use client";

import { ProductImage } from "@/components/common/ProductImage";
import { formatInr } from "@/lib/format";
import type { CatalogItem } from "@/lib/api";
import { Title, Body } from "@/components/ui";

type FeaturedGridProps = {
  items: CatalogItem[];
  onQuickSearch?: (query: string) => void;
};

export function FeaturedGrid({ items, onQuickSearch }: FeaturedGridProps) {
  const [featured, ...rest] = items;
  const side = rest.slice(0, 3);

  if (!featured) return null;

  return (
    <section className="mt-[var(--space-section)]">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <Title as="h2">In store now</Title>
          <Body className="mt-1.5 max-w-[40ch]">
            Browse the floor — or describe what you meant above.
          </Body>
        </div>
        {onQuickSearch ? (
          <button
            type="button"
            onClick={() =>
              onQuickSearch("waterproof hiking boots under 4000")
            }
            className="hidden text-sm font-semibold text-signal transition-colors hover:text-signal-hover sm:inline"
          >
            Try a vague search →
          </button>
        ) : null}
      </div>

      <div className="grid gap-3 md:grid-cols-2 md:gap-4 lg:grid-cols-12">
        <article className="group overflow-hidden rounded-[20px] border border-line bg-paper shadow-elev-1 md:col-span-1 lg:col-span-7">
          <div className="relative aspect-[16/11] bg-chalk">
            <ProductImage
              src={featured.image_url}
              alt={featured.name}
              priority
              sizes="(max-width: 768px) 100vw, 60vw"
            />
          </div>
          <div className="flex items-end justify-between gap-4 p-5 md:p-6">
            <div>
              <h3 className="font-display text-xl text-ink md:text-2xl">
                {featured.name}
              </h3>
              <p className="mt-1 text-sm text-muted">
                {formatInr(featured.price, featured.currency)}
              </p>
            </div>
            <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted">
              Featured
            </span>
          </div>
        </article>

        <div className="grid gap-3 sm:grid-cols-3 md:col-span-1 md:grid-cols-1 lg:col-span-5 lg:gap-4">
          {side.map((item, index) => (
            <article
              key={item.sku_id}
              className="group flex overflow-hidden rounded-2xl border border-line bg-paper shadow-elev-1 sm:flex-col lg:flex-row"
              style={{
                animation: `resultIn var(--motion-results-duration) var(--ease-out) both`,
                animationDelay: `calc(${index + 1} * var(--motion-results-stagger))`,
              }}
            >
              <div className="relative aspect-square w-28 shrink-0 bg-chalk sm:aspect-[4/3] sm:w-full lg:w-28 lg:aspect-square">
                <ProductImage
                  src={item.image_url}
                  alt={item.name}
                  sizes="120px"
                />
              </div>
              <div className="flex flex-1 flex-col justify-center p-3.5">
                <h3 className="text-sm font-semibold leading-snug text-ink">
                  {item.name}
                </h3>
                <p className="mt-1 text-[13px] text-muted">
                  {formatInr(item.price, item.currency)}
                </p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

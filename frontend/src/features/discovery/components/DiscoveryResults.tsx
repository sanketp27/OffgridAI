"use client";

import { ProductCardSkeleton, Title } from "@/components/ui";
import { NearMatchBanner } from "@/features/discovery/components/NearMatchBanner";
import { ResultCard } from "@/features/discovery/components/ResultCard";
import type { SearchResponse, SearchResult } from "@/lib/api";
import type { ReactNode } from "react";

type DiscoveryResultsProps = {
  data: SearchResponse | undefined;
  isLoading: boolean;
  queryLabel?: string;
  selectedSkuId?: string | null;
  onChoose: (result: SearchResult) => void;
  onClear: () => void;
  belowResults?: ReactNode;
  aboveResults?: ReactNode;
};

export function DiscoveryResults({
  data,
  isLoading,
  queryLabel,
  selectedSkuId,
  onChoose,
  onClear,
  belowResults,
  aboveResults,
}: DiscoveryResultsProps) {
  if (isLoading) {
    return (
      <section className="mt-12">
        <div className="mb-6 h-7 w-48 animate-pulse rounded-md bg-line/70" />
        <div className="grid gap-4 md:grid-cols-3">
          <ProductCardSkeleton />
          <ProductCardSkeleton />
          <ProductCardSkeleton />
        </div>
      </section>
    );
  }

  if (!data) return null;

  const showNear = data.results.some((r) => r.match_quality !== "exact");

  return (
    <section className="mt-12">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <Title as="h2">Matches for you</Title>
          {queryLabel ? (
            <p className="mt-1.5 text-sm text-muted">
              Intent: <span className="font-medium text-ink">{queryLabel}</span>
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onClear}
          className="text-sm font-semibold text-muted transition-colors hover:text-ink"
        >
          Clear results
        </button>
      </div>

      {aboveResults}

      {showNear ? <NearMatchBanner className="mb-6" /> : null}

      <div className="grid gap-4 md:grid-cols-3">
        {data.results.map((result, index) => (
          <ResultCard
            key={result.sku_id}
            result={result}
            index={index}
            selected={selectedSkuId === result.sku_id}
            onChoose={onChoose}
          />
        ))}
      </div>

      {belowResults ? <div className="mt-6">{belowResults}</div> : null}
    </section>
  );
}

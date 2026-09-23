"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  getCatalog,
  searchProducts,
  type RescueOption,
  type SearchResult,
} from "@/lib/api";
import { AppShell } from "@/components/common/AppShell";
import { Display, Body, Eyebrow } from "@/components/ui";
import { FeaturedGrid } from "@/features/storefront/components/FeaturedGrid";
import { DiscoverySearch } from "@/features/discovery/components/DiscoverySearch";
import { DiscoveryResults } from "@/features/discovery/components/DiscoveryResults";
import { FitCheckPanel } from "@/features/fit-check/components/FitCheckPanel";
import { StockoutRescuePanel } from "@/features/rescue/components/StockoutRescuePanel";
import { CartStrip } from "@/features/session/components/CartStrip";
import { useSession } from "@/features/session/SessionProvider";

export function StorefrontScreen() {
  const { sessionId, setSession, addToCart } = useSession();
  const [queryLabel, setQueryLabel] = useState<string | undefined>();
  const [chosen, setChosen] = useState<SearchResult | null>(null);
  const [fitResolved, setFitResolved] = useState(false);
  const [acceptedRescue, setAcceptedRescue] = useState<string | null>(null);

  const catalog = useQuery({
    queryKey: ["catalog", "featured"],
    queryFn: getCatalog,
  });

  const search = useMutation({
    mutationFn: searchProducts,
    onSuccess: (data) => {
      setSession(data.session_id, data.event_id);
    },
  });

  const fitPrompt = search.data?.fit_check;
  const rescue = search.data?.rescue;

  const showFitCheck = useMemo(() => {
    if (!chosen || !fitPrompt?.triggered || fitResolved) return false;
    if (!fitPrompt.sku_id) return true;
    return chosen.sku_id === fitPrompt.sku_id;
  }, [chosen, fitPrompt, fitResolved]);

  const onSearch = (input: { queryText?: string; imageBase64?: string }) => {
    setChosen(null);
    setFitResolved(false);
    setAcceptedRescue(null);
    setQueryLabel(
      input.queryText?.trim() ||
        (input.imageBase64 ? "Photo search" : undefined),
    );
    search.mutate({
      session_id: sessionId,
      query_text: input.queryText,
      image_base64: input.imageBase64 ?? null,
    });
  };

  const onChoose = (result: SearchResult) => {
    addToCart(result);
    setChosen(result);
    setFitResolved(false);
  };

  const onAcceptRescue = (option: RescueOption) => {
    setAcceptedRescue(option.option_id);
    if (option.sku_id && option.price != null) {
      addToCart({
        sku_id: option.sku_id,
        name: option.name,
        price: option.price,
        currency: option.currency ?? "INR",
        image_url:
          option.image_url || "/products/rn-210.svg",
      });
    }
  };

  const onClear = () => {
    search.reset();
    setQueryLabel(undefined);
    setChosen(null);
    setFitResolved(false);
    setAcceptedRescue(null);
  };

  return (
    <AppShell tone="shop">
      <main className="page-shell flex-1 pb-28 pt-12 md:pt-16">
        <div className="max-w-[720px]">
          <Eyebrow>Smart discovery</Eyebrow>
          <Display className="mt-4 max-w-[14ch]">
            Find it. Or we&apos;ll rescue the journey.
          </Display>
          <Body className="mt-5 max-w-[44ch]">
            Vague words, slang, or a photo — grounded SKUs, fit-checks, and stockout
            rescues. Failed moments become merchant signal.
          </Body>
        </div>

        <DiscoverySearch
          className="mt-10 max-w-[780px]"
          onSearch={onSearch}
          isLoading={search.isPending}
        />

        {search.isError ? (
          <p className="mt-6 text-sm text-coral" role="alert">
            Something went wrong searching. Try again.
          </p>
        ) : null}

        <DiscoveryResults
          data={search.data}
          isLoading={search.isPending}
          queryLabel={queryLabel}
          selectedSkuId={chosen?.sku_id}
          onChoose={onChoose}
          onClear={onClear}
          aboveResults={
            rescue?.triggered ? (
              <StockoutRescuePanel
                rescue={rescue}
                onAccept={onAcceptRescue}
                acceptedId={acceptedRescue}
              />
            ) : null
          }
          belowResults={
            showFitCheck && chosen && fitPrompt ? (
              <FitCheckPanel
                product={chosen}
                prompt={fitPrompt}
                onResolved={() => setFitResolved(true)}
              />
            ) : chosen && !showFitCheck && fitResolved ? (
              <p
                role="status"
                className="rounded-2xl border border-signal/25 bg-signal-soft px-4 py-3 text-sm text-ink"
              >
                Fit preference saved. Open the bag — or continue to Merchant insights.
              </p>
            ) : chosen && !showFitCheck ? (
              <p
                role="status"
                className="rounded-2xl border border-signal/25 bg-signal-soft px-4 py-3 text-sm text-ink"
              >
                Added to bag. No fit-check needed for this item.
              </p>
            ) : null
          }
        />

        {!search.data && !search.isPending ? (
          catalog.isLoading ? (
            <section className="mt-[var(--space-section)]">
              <div className="mb-8 h-8 w-48 animate-pulse rounded-md bg-line/70" />
              <div className="grid gap-4 lg:grid-cols-12">
                <div className="aspect-[16/11] animate-pulse rounded-[20px] bg-line/50 lg:col-span-7" />
                <div className="grid gap-4 lg:col-span-5">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div
                      key={i}
                      className="h-24 animate-pulse rounded-2xl bg-line/50"
                    />
                  ))}
                </div>
              </div>
            </section>
          ) : (
            <FeaturedGrid
              items={catalog.data ?? []}
              onQuickSearch={(q) => onSearch({ queryText: q })}
            />
          )
        ) : null}
      </main>

      <CartStrip />
    </AppShell>
  );
}

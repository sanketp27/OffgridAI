"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import Link from "next/link";
import { Button, EmptyState, InsightCardSkeleton, Eyebrow, Display, Body } from "@/components/ui";
import { AppShell } from "@/components/common/AppShell";
import { InsightCard } from "@/features/insights/components/InsightCard";
import { generateInsights, type GenerateInsightsResponse } from "@/lib/api";
import { formatInr } from "@/lib/format";
import { useSession } from "@/features/session/SessionProvider";
import { LoopMark } from "@/components/common/LoopMark";

export function MerchantScreen() {
  const [data, setData] = useState<GenerateInsightsResponse | null>(null);
  const { sessionId, cart } = useSession();

  const generate = useMutation({
    mutationFn: () => generateInsights({ time_window_days: 7 }),
    onSuccess: setData,
  });

  const totalRisk =
    data?.insights.reduce((sum, i) => sum + i.est_revenue_at_risk, 0) ?? 0;

  const hasShopperTrail = Boolean(sessionId) || cart.length > 0;

  return (
    <AppShell tone="merchant" showBag={false}>
      <main className="page-shell flex-1 py-12 md:py-16">
        {hasShopperTrail ? (
          <div className="mb-8 rounded-2xl border border-line bg-paper px-4 py-3 text-sm text-ink shadow-elev-1">
            Shopper session active
            {sessionId ? (
              <span className="text-muted">
                {" "}
                · {sessionId.slice(0, 14)}…
              </span>
            ) : null}
            {cart.length > 0 ? (
              <span className="text-muted"> · bag {cart.length}</span>
            ) : null}
            <span className="text-muted">
              {" "}
              — Generate Insights to close the loop.
            </span>
          </div>
        ) : null}

        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="max-w-[34rem]">
            <Eyebrow>OffgridAI · Merchant</Eyebrow>
            <Display as="h1" className="mt-3 max-w-[16ch]">
              Demand from failed journeys
            </Display>
            <Body className="mt-4">
              Grounded briefs from shopper events — unmet demand, fit flips, and stock
              gaps. Confirm nothing here invents numbers.
            </Body>
          </div>
          <Button
            size="lg"
            isLoading={generate.isPending}
            onClick={() => generate.mutate()}
          >
            Generate Insights
          </Button>
        </div>

        {data && data.insights.length > 0 ? (
          <div className="mt-10 overflow-hidden rounded-[20px] border border-line bg-ink text-paper shadow-elev-2">
            <div className="grid gap-6 p-6 sm:grid-cols-3 md:p-8">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-paper/55">
                  Revenue at risk
                </p>
                <p
                  className="font-display mt-2 text-3xl tabular-nums"
                  style={{ color: "var(--coral-soft)" }}
                >
                  {formatInr(totalRisk)}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-paper/55">
                  Events processed
                </p>
                <p className="mt-2 text-3xl font-semibold tabular-nums">
                  {data.event_count_processed}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-paper/55">
                  Signals
                </p>
                <p className="mt-2 text-3xl font-semibold tabular-nums">
                  {data.insights.length}
                </p>
              </div>
            </div>
          </div>
        ) : null}

        {generate.isPending ? (
          <div className="mt-8 space-y-4">
            <InsightCardSkeleton />
            <InsightCardSkeleton />
            <InsightCardSkeleton />
          </div>
        ) : null}

        {generate.isError ? (
          <p className="mt-8 text-sm text-coral" role="alert">
            Couldn’t generate insights. Check API connection and try again.
          </p>
        ) : null}

        {!generate.isPending && !data ? (
          <div className="mt-12 rounded-[20px] border border-dashed border-line bg-paper px-6 py-12 text-center shadow-elev-1">
            <LoopMark className="mx-auto" />
            <h3 className="font-display mt-6 text-2xl text-ink">Ready when you are</h3>
            <p className="mx-auto mt-2 max-w-[40ch] text-sm leading-relaxed text-muted">
              {hasShopperTrail
                ? "A shopper session is on the trail. Generate Insights to turn it into Monday-morning actions."
                : "Complete a storefront discovery or fit-check first — then close the loop here."}
            </p>
            {!hasShopperTrail ? (
              <Link href="/" className="mt-6 inline-block">
                <Button variant="secondary">Open storefront</Button>
              </Link>
            ) : (
              <Button className="mt-6" onClick={() => generate.mutate()}>
                Generate Insights
              </Button>
            )}
          </div>
        ) : null}

        {!generate.isPending && data && data.insights.length === 0 ? (
          <EmptyState
            className="mt-10"
            title="No signals yet"
            description="Run a shopper session on the storefront first — failed intent becomes merchant intelligence."
          />
        ) : null}

        {data && data.insights.length > 0 ? (
          <div className="mt-8 space-y-4">
            {data.insights.map((insight, index) => (
              <InsightCard
                key={insight.insight_id}
                insight={insight}
                index={index}
              />
            ))}
          </div>
        ) : null}

        <p className="mt-12 text-sm text-muted">
          Need another shopper pass?{" "}
          <Link href="/" className="font-semibold text-signal hover:text-signal-hover">
            Open storefront
          </Link>
        </p>
      </main>
    </AppShell>
  );
}

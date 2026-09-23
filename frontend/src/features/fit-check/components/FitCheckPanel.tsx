"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button, Chip, Input } from "@/components/ui";
import { submitFitCheck, type FitCheckPrompt, type SearchResult } from "@/lib/api";
import { MOCK_CATALOG } from "@/lib/api/mock/catalog";
import { useSession } from "@/features/session/SessionProvider";
import { cn } from "@/lib/cn";
import Link from "next/link";

const QUICK_ANSWERS = [
  { label: "Size up to 9.5", value: "I'll size up to 9.5" },
  { label: "Keep size 9", value: "Standard size 9 is fine" },
  { label: "Wider toe box", value: "Prefer a wider toe box" },
] as const;

type FitCheckPanelProps = {
  product: SearchResult;
  prompt: FitCheckPrompt;
  className?: string;
  onResolved?: (resolution: string) => void;
};

export function FitCheckPanel({
  product,
  prompt,
  className,
  onResolved,
}: FitCheckPanelProps) {
  const { sessionId, lastEventId, setLastEventId, replaceInCart, addToCart } =
    useSession();
  const [answer, setAnswer] = useState("");
  const [doneMessage, setDoneMessage] = useState<string | null>(null);
  const [activeQuick, setActiveQuick] = useState<string | null>(null);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, []);

  const mutation = useMutation({
    mutationFn: submitFitCheck,
    onSuccess: (res) => {
      setLastEventId(res.event_id);

      const nextSku = res.new_sku_id ?? product.sku_id;
      const catalogHit = MOCK_CATALOG.find((c) => c.sku_id === nextSku);
      const line = {
        sku_id: nextSku,
        name: catalogHit?.name ?? `${product.name} (updated)`,
        price: catalogHit?.price ?? product.price,
        currency: catalogHit?.currency ?? product.currency,
        image_url: catalogHit?.image_url ?? product.image_url,
      };

      if (res.resolution === "size_changed" && res.new_sku_id) {
        replaceInCart(product.sku_id, line);
        setDoneMessage(
          `Bag updated to ${line.name}. Fit preference logged for the merchant.`,
        );
      } else {
        addToCart(line);
        setDoneMessage("Size confirmed. Bag updated — preference logged.");
      }

      onResolved?.(res.resolution);
    },
  });

  const canSubmit =
    Boolean(sessionId && lastEventId && prompt.sku_id && answer.trim()) &&
    !mutation.isPending &&
    !doneMessage;

  const submit = (text: string) => {
    if (!sessionId || !lastEventId || !prompt.sku_id || !text.trim()) return;
    mutation.mutate({
      session_id: sessionId,
      sku_id: prompt.sku_id,
      response_text: text.trim(),
      event_id: lastEventId,
    });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(answer);
  };

  if (!prompt.triggered || !prompt.question) return null;

  return (
    <aside
      ref={panelRef}
      className={cn(
        "rounded-[20px] border border-amber/40 bg-amber-soft p-5 shadow-elev-1 md:p-6",
        className,
      )}
      style={{
        animation: `fitCheckIn var(--motion-fitcheck-duration) var(--ease-out) both`,
      }}
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone="amber">Fit-check</Chip>
        <span className="text-[12px] font-medium uppercase tracking-[0.1em] text-ink/65">
          One question before you buy
        </span>
      </div>

      <p className="font-display mt-3 text-xl text-ink md:text-[1.35rem]">
        {prompt.question}
      </p>
      <p className="mt-1.5 text-sm text-ink/70">
        About <span className="font-semibold text-ink">{product.name}</span> · SKU{" "}
        {product.sku_id}
      </p>

      {doneMessage ? (
        <div className="mt-5 space-y-3">
          <p
            role="status"
            className="rounded-2xl border border-signal/25 bg-paper px-4 py-3 text-sm text-ink"
          >
            {doneMessage}
          </p>
          <Link
            href="/merchant"
            className="inline-flex text-sm font-semibold text-signal hover:text-signal-hover"
          >
            See what merchants will learn →
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="mt-5 space-y-4">
          <div
            className="grid gap-2 sm:grid-cols-3"
            role="group"
            aria-label="Quick fit answers"
          >
            {QUICK_ANSWERS.map((q) => (
              <button
                key={q.value}
                type="button"
                disabled={mutation.isPending}
                onClick={() => {
                  setActiveQuick(q.value);
                  setAnswer(q.value);
                  submit(q.value);
                }}
                className={cn(
                  "rounded-xl border px-3 py-3 text-left text-[13px] font-medium transition-colors",
                  activeQuick === q.value
                    ? "border-ink bg-paper text-ink"
                    : "border-amber/40 bg-paper/80 text-ink hover:border-ink/30",
                  "disabled:opacity-50",
                )}
              >
                {q.label}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <Input
              label="Or type your answer"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="e.g. size up to 9.5"
              className="flex-1"
              disabled={mutation.isPending}
            />
            <Button
              type="submit"
              isLoading={mutation.isPending}
              disabled={!canSubmit}
            >
              Confirm fit
            </Button>
          </div>
          {mutation.isError ? (
            <p className="text-sm text-coral" role="alert">
              Couldn’t save fit preference. Try again.
            </p>
          ) : null}
        </form>
      )}
    </aside>
  );
}

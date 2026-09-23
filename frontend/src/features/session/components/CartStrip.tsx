"use client";

import { useState } from "react";
import { useSession } from "@/features/session/SessionProvider";
import { ProductImage } from "@/components/common/ProductImage";
import { formatInr } from "@/lib/format";
import { cn } from "@/lib/cn";

export function CartStrip() {
  const { cart, clearCart } = useSession();
  const [open, setOpen] = useState(false);

  if (cart.length === 0) return null;

  const total = cart.reduce((sum, line) => sum + line.price, 0);

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center p-4 md:p-6">
      <div
        className={cn(
          "pointer-events-auto w-full max-w-md overflow-hidden rounded-[20px] border border-line/80",
          "bg-paper/90 shadow-elev-2 backdrop-blur-xl",
          "animate-[bagPulse_var(--motion-bag-pulse)_var(--ease-out)]",
        )}
      >
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center gap-3 px-4 py-3.5 text-left"
          aria-expanded={open}
        >
          <div className="flex -space-x-2">
            {cart.slice(0, 3).map((line) => (
              <div
                key={line.sku_id}
                className="relative h-9 w-9 overflow-hidden rounded-full border-2 border-paper bg-chalk"
              >
                <ProductImage src={line.image_url} alt="" sizes="36px" />
              </div>
            ))}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink">
              Bag · {cart.length} item{cart.length === 1 ? "" : "s"}
            </p>
            <p className="truncate text-[12px] text-muted">
              {formatInr(total)} · updates without reload
            </p>
          </div>
          <span className="text-sm font-semibold text-signal">
            {open ? "Hide" : "View"}
          </span>
        </button>

        {open ? (
          <div className="border-t border-line px-4 py-3">
            <ul className="space-y-3">
              {cart.map((line) => (
                <li key={line.sku_id} className="flex items-center gap-3">
                  <div className="relative h-12 w-12 overflow-hidden rounded-xl bg-chalk">
                    <ProductImage src={line.image_url} alt="" sizes="48px" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">
                      {line.name}
                    </p>
                    <p className="text-[12px] text-muted">
                      {line.sku_id} · {formatInr(line.price, line.currency)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={clearCart}
              className="mt-3 text-[12px] font-medium text-muted hover:text-ink"
            >
              Clear bag
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "@/features/session/SessionProvider";
import { cn } from "@/lib/cn";

type StorefrontHeaderProps = {
  className?: string;
};

export function StorefrontHeader({ className }: StorefrontHeaderProps) {
  const { cart } = useSession();
  const pathname = usePathname();

  const linkClass = (href: string) =>
    cn(
      "transition-colors hover:text-ink",
      pathname === href ? "font-semibold text-ink" : "text-muted",
    );

  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b border-line/70 bg-chalk/85 backdrop-blur-md",
        className,
      )}
    >
      <div className="mx-auto flex h-16 w-full max-w-[1120px] items-center justify-between px-5 md:px-10">
        <Link href="/" className="flex items-baseline gap-2.5 no-underline">
          <span
            className="text-[1.4rem] tracking-[-0.03em] text-ink"
            style={{ fontFamily: "var(--font-family-display)" }}
          >
            GridMart
          </span>
          <span className="hidden text-[11px] font-medium tracking-[0.04em] text-muted sm:inline">
            powered by OffgridAI
          </span>
        </Link>

        <div className="flex items-center gap-4 text-sm md:gap-5">
          <Link href="/merchant" className={linkClass("/merchant")}>
            Merchant
          </Link>
          <Link href="/associate" className={linkClass("/associate")}>
            Associate
          </Link>
          <div
            className="flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5"
            aria-live="polite"
          >
            <span className="text-muted">Bag</span>
            <span className="min-w-[1.25rem] text-center font-semibold tabular-nums text-ink">
              {cart.length}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "@/features/session/SessionProvider";
import { IconBag } from "@/components/ui";
import { cn } from "@/lib/cn";

type AppShellProps = {
  children: React.ReactNode;
  /** shop = teal wash; merchant = ink/ops; associate = minimal floor */
  tone?: "shop" | "merchant" | "associate";
  showBag?: boolean;
  className?: string;
};

export function AppShell({
  children,
  tone = "shop",
  showBag = true,
  className,
}: AppShellProps) {
  const { cart } = useSession();
  const pathname = usePathname();

  const linkClass = (href: string) =>
    cn(
      "rounded-lg px-2 py-1 transition-colors",
      pathname === href
        ? "font-semibold text-ink"
        : "text-muted hover:text-ink",
    );

  return (
    <div className={cn("relative flex min-h-full flex-1 flex-col", className)}>
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute inset-x-0 top-0 h-[440px]",
          tone === "shop" &&
            "bg-[radial-gradient(ellipse_at_top,_rgba(10,127,108,0.09),_transparent_58%)]",
          tone === "merchant" &&
            "bg-[radial-gradient(ellipse_at_top,_rgba(17,17,20,0.06),_transparent_55%)]",
          tone === "associate" && "bg-transparent",
        )}
      />

      <header className="sticky top-0 z-40 border-b border-line/60 bg-chalk/80 backdrop-blur-xl">
        <div className="page-shell flex h-[4.25rem] items-center justify-between">
          <Link href="/" className="flex items-baseline gap-2.5 no-underline">
            <span className="font-display text-[1.45rem] text-ink">GridMart</span>
            <span className="hidden text-[11px] font-medium tracking-[0.04em] text-muted sm:inline">
              powered by OffgridAI
            </span>
          </Link>

          <nav className="flex items-center gap-1 text-sm md:gap-2">
            <Link href="/merchant" className={linkClass("/merchant")}>
              Merchant
            </Link>
            <Link href="/associate" className={linkClass("/associate")}>
              Associate
            </Link>
            {showBag ? (
              <div
                className={cn(
                  "ml-2 flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5 shadow-elev-1",
                  cart.length > 0 && "animate-[bagPulse_var(--motion-bag-pulse)_var(--ease-out)]",
                )}
                aria-live="polite"
              >
                <IconBag size={16} className="text-muted" />
                <span className="min-w-[1rem] text-center text-sm font-semibold tabular-nums text-ink">
                  {cart.length}
                </span>
              </div>
            ) : null}
          </nav>
        </div>
      </header>

      <div className="relative flex flex-1 flex-col">{children}</div>
    </div>
  );
}

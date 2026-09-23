import { cn } from "@/lib/cn";

type NearMatchBannerProps = {
  className?: string;
};

export function NearMatchBanner({ className }: NearMatchBannerProps) {
  return (
    <div
      role="status"
      className={cn(
        "flex overflow-hidden rounded-2xl border border-signal/20 bg-paper shadow-elev-1",
        className,
      )}
    >
      <div className="flex w-[7.5rem] shrink-0 flex-col items-start justify-center bg-signal px-4 py-4 text-white sm:w-36">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-80">
          Status
        </span>
        <span className="mt-1 font-display text-xl leading-tight">Rescued</span>
      </div>
      <div className="flex-1 bg-signal-soft/60 px-4 py-4 md:px-5">
        <p className="text-sm font-semibold text-ink">No exact match in catalog</p>
        <p className="mt-1 max-w-[48ch] text-sm leading-relaxed text-ink/75">
          Closest grounded hits below — every near-miss still becomes a demand signal
          for the merchant.
        </p>
      </div>
    </div>
  );
}

import { cn } from "@/lib/cn";

/** Minimal loop mark: intent → rescue → insight */
export function LoopMark({ className }: { className?: string }) {
  return (
    <svg
      width="72"
      height="72"
      viewBox="0 0 72 72"
      fill="none"
      className={cn("text-signal", className)}
      aria-hidden
    >
      <circle cx="36" cy="36" r="28" stroke="currentColor" strokeWidth="1.5" opacity="0.35" />
      <path
        d="M36 14v10M36 48v10M14 36h10M48 36h10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.35"
      />
      <circle cx="36" cy="24" r="4" fill="currentColor" />
      <circle cx="48" cy="42" r="4" fill="currentColor" opacity="0.7" />
      <circle cx="24" cy="42" r="4" fill="currentColor" opacity="0.45" />
      <path
        d="M36 28c8 2 12 8 12 14M48 42c-6 6-14 8-20 6M24 42c2-8 8-14 12-18"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.55"
      />
    </svg>
  );
}

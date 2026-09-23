import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type SkeletonProps = HTMLAttributes<HTMLDivElement> & {
  /** Optional fixed height class e.g. h-4 */
  rounded?: "md" | "lg" | "xl" | "full";
};

const roundedClass = {
  md: "rounded-md",
  lg: "rounded-lg",
  xl: "rounded-xl",
  full: "rounded-full",
} as const;

/** Layout-stable loading placeholder — match final geometry to avoid CLS. */
export function Skeleton({
  className,
  rounded = "lg",
  ...props
}: SkeletonProps) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-pulse bg-line/70",
        roundedClass[rounded],
        className,
      )}
      {...props}
    />
  );
}

export function ProductCardSkeleton() {
  return (
    <div className="rounded-xl border border-line bg-paper p-4">
      <Skeleton className="aspect-[4/3] w-full" rounded="xl" />
      <Skeleton className="mt-4 h-4 w-3/4" />
      <Skeleton className="mt-2 h-3 w-1/2" />
      <Skeleton className="mt-4 h-10 w-full" rounded="xl" />
    </div>
  );
}

export function InsightCardSkeleton() {
  return (
    <div className="rounded-xl border border-line bg-paper p-5">
      <Skeleton className="h-5 w-28" rounded="full" />
      <Skeleton className="mt-4 h-5 w-2/3" />
      <Skeleton className="mt-3 h-3 w-full" />
      <Skeleton className="mt-2 h-3 w-5/6" />
    </div>
  );
}

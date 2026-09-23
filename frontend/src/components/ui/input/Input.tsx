import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  hint?: string;
  error?: string;
  leftSlot?: ReactNode;
  rightSlot?: ReactNode;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      hint,
      error,
      leftSlot,
      rightSlot,
      className,
      id,
      disabled,
      ...props
    },
    ref,
  ) => {
    const inputId = id ?? props.name;

    return (
      <label className={cn("flex w-full flex-col gap-1.5", className)}>
        {label ? (
          <span className="text-[13px] font-medium text-ink">{label}</span>
        ) : null}
        <span
          className={cn(
            "flex h-12 items-center gap-2 rounded-xl border bg-paper px-3.5 transition-colors",
            error ? "border-coral" : "border-line focus-within:border-signal",
            disabled && "opacity-60",
          )}
        >
          {leftSlot ? (
            <span className="shrink-0 text-muted">{leftSlot}</span>
          ) : null}
          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            className="min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-muted/80"
            aria-invalid={Boolean(error) || undefined}
            {...props}
          />
          {rightSlot ? (
            <span className="shrink-0 text-muted">{rightSlot}</span>
          ) : null}
        </span>
        {error ? (
          <span className="text-[12px] text-coral">{error}</span>
        ) : hint ? (
          <span className="text-[12px] text-muted">{hint}</span>
        ) : null}
      </label>
    );
  },
);

Input.displayName = "Input";

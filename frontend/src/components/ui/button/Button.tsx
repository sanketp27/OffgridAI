import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  fullWidth?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
};

const variantClass: Record<ButtonVariant, string> = {
  primary:
    "bg-signal text-white shadow-elev-1 hover:bg-signal-hover active:translate-y-px disabled:bg-signal/45 disabled:shadow-none",
  secondary:
    "bg-paper text-ink border border-line hover:bg-chalk/80 active:bg-chalk disabled:opacity-50",
  ghost:
    "bg-transparent text-ink hover:bg-ink/[0.04] active:bg-ink/[0.06] disabled:opacity-50",
  danger:
    "bg-coral text-white hover:bg-coral/90 active:translate-y-px disabled:bg-coral/50",
};

const sizeClass: Record<ButtonSize, string> = {
  sm: "h-9 min-h-9 px-3.5 text-[13px] gap-1.5 rounded-[10px]",
  md: "h-11 min-h-11 px-5 text-sm gap-2 rounded-xl",
  lg: "h-12 min-h-12 px-6 text-sm gap-2 rounded-xl",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      isLoading = false,
      fullWidth = false,
      leftIcon,
      rightIcon,
      className,
      disabled,
      children,
      type = "button",
      ...props
    },
    ref,
  ) => {
    const isDisabled = disabled || isLoading;

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={isLoading || undefined}
        className={cn(
          "inline-flex items-center justify-center font-semibold transition-[color,background-color,box-shadow,transform]",
          "duration-[var(--duration-fast)] ease-[var(--ease-out)]",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal",
          "disabled:cursor-not-allowed",
          variantClass[variant],
          sizeClass[size],
          fullWidth && "w-full",
          className,
        )}
        {...props}
      >
        {isLoading ? (
          <span
            className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent"
            aria-hidden
          />
        ) : (
          leftIcon
        )}
        {children}
        {!isLoading && rightIcon}
      </button>
    );
  },
);

Button.displayName = "Button";

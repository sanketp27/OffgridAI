import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

type TextProps = HTMLAttributes<HTMLElement> & {
  children: ReactNode;
  as?: "h1" | "h2" | "h3" | "p" | "span";
};

export function Eyebrow({ className, as: Tag = "p", ...props }: TextProps) {
  return <Tag className={cn("text-eyebrow", className)} {...props} />;
}

export function Display({ className, as: Tag = "h1", ...props }: TextProps) {
  return <Tag className={cn("text-display", className)} {...props} />;
}

export function Title({ className, as: Tag = "h2", ...props }: TextProps) {
  return <Tag className={cn("text-title", className)} {...props} />;
}

export function Body({ className, as: Tag = "p", ...props }: TextProps) {
  return (
    <Tag
      className={cn("text-[15px] leading-relaxed text-muted md:text-base", className)}
      {...props}
    />
  );
}

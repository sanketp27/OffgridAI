import { clsx, type ClassValue } from "clsx";

/** Merge class names; filters falsy values. */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

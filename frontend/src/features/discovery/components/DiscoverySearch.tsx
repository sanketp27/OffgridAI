"use client";

import {
  useRef,
  useState,
  type FormEvent,
  type ChangeEvent,
  type KeyboardEvent,
} from "react";
import { Button, IconCamera, IconSearch } from "@/components/ui";
import { cn } from "@/lib/cn";

const SUGGESTIONS = [
  { label: "Vague hiking intent", query: "waterproof hiking boots under 4000" },
  { label: "Need it today", query: "black running shoes size 9 today" },
  { label: "Cozy home", query: "something cozy for the living room" },
] as const;

type DiscoverySearchProps = {
  onSearch: (input: { queryText?: string; imageBase64?: string }) => void;
  isLoading?: boolean;
  className?: string;
};

export function DiscoverySearch({
  onSearch,
  isLoading,
  className,
}: DiscoverySearchProps) {
  const [query, setQuery] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const submit = (text = query) => {
    const trimmed = text.trim();
    if (!trimmed && !imageBase64) return;
    onSearch({
      queryText: trimmed || undefined,
      imageBase64: imageBase64 ?? undefined,
    });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit();
  };

  const onFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) return;
    if (file.size > 4 * 1024 * 1024) {
      window.alert("Please choose an image under 4MB.");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      setPreview(result);
      const base64 = result.includes(",") ? result.split(",")[1]! : result;
      setImageBase64(base64);
    };
    reader.readAsDataURL(file);
  };

  const clearImage = () => {
    setPreview(null);
    setImageBase64(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={cn("w-full", className)}>
      <form onSubmit={onSubmit}>
        <div
          className={cn(
            "rounded-[20px] border border-line/80 bg-paper p-2 shadow-elev-2",
            "transition-[box-shadow,border-color] duration-[var(--duration-base)]",
            "focus-within:border-signal/40 focus-within:shadow-[0_0_0_4px_var(--focus-ring),var(--elev-2)]",
          )}
        >
          {preview ? (
            <div className="mb-2 flex items-center gap-3 rounded-2xl bg-chalk px-3 py-2.5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview}
                alt="Upload preview"
                className="h-14 w-14 rounded-xl object-cover"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">
                  Photo attached
                </p>
                <p className="text-[12px] text-muted">
                  Grounded to catalog SKUs — never a dead end.
                </p>
              </div>
              <button
                type="button"
                onClick={clearImage}
                className="text-sm font-medium text-muted hover:text-ink"
              >
                Remove
              </button>
            </div>
          ) : null}

          <div className="flex items-center gap-1">
            <span className="hidden pl-3 text-muted sm:inline">
              <IconSearch size={18} />
            </span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Describe what you meant — slang, budget, or a photo…"
              className="h-14 min-w-0 flex-1 bg-transparent px-3 text-[15px] text-ink outline-none placeholder:text-muted/65 md:text-base"
              aria-label="Search products"
              disabled={isLoading}
            />
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="sr-only"
              onChange={onFile}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-muted transition-colors hover:bg-chalk hover:text-ink"
              aria-label="Upload product photo"
              title="Upload photo"
            >
              <IconCamera />
            </button>
            <Button
              type="submit"
              size="lg"
              isLoading={isLoading}
              className="mr-0.5 shrink-0"
              disabled={isLoading || (!query.trim() && !imageBase64)}
            >
              Search
            </Button>
          </div>
        </div>
      </form>

      <div className="mt-5 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.query}
            type="button"
            onClick={() => {
              setQuery(s.query);
              submit(s.query);
            }}
            disabled={isLoading}
            className="rounded-full border border-line bg-paper/90 px-3.5 py-2 text-[12px] font-medium text-muted shadow-elev-1 transition-colors hover:border-ink/15 hover:text-ink disabled:opacity-50"
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}

"use client";

import { useMutation } from "@tanstack/react-query";
import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import {
  assessReturn,
  confirmReturn,
  type ReturnAssessment,
} from "@/lib/api";
import {
  Button,
  Chip,
  Input,
  Eyebrow,
  Display,
  Body,
  IconCamera,
} from "@/components/ui";
import { AppShell } from "@/components/common/AppShell";
import { cn } from "@/lib/cn";

const DISPOSITIONS = [
  "restock",
  "refurbish_and_relist",
  "liquidate",
  "hold_for_review",
] as const;

const STEPS = ["Photo", "Assess", "Confirm"] as const;

export function AssociateScreen() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [orderId, setOrderId] = useState("ORD-00123");
  const [preview, setPreview] = useState<string | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [assessment, setAssessment] = useState<ReturnAssessment | null>(null);
  const [disposition, setDisposition] = useState<string>("refurbish_and_relist");
  const [confirmMsg, setConfirmMsg] = useState<string | null>(null);

  const stepIndex = confirmMsg ? 2 : assessment ? 1 : 0;

  const assess = useMutation({
    mutationFn: assessReturn,
    onSuccess: (data) => {
      setAssessment(data);
      setDisposition(data.recommended_disposition);
      setConfirmMsg(null);
    },
  });

  const confirm = useMutation({
    mutationFn: confirmReturn,
    onSuccess: (data) => setConfirmMsg(data.message),
  });

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
      setImageBase64(result.includes(",") ? result.split(",")[1]! : result);
    };
    reader.readAsDataURL(file);
  };

  const onAssess = (e: FormEvent) => {
    e.preventDefault();
    if (!imageBase64 || !orderId.trim()) return;
    assess.mutate({ order_id: orderId.trim(), image_base64: imageBase64 });
  };

  return (
    <AppShell tone="associate" showBag={false}>
      <main className="mx-auto flex w-full max-w-[440px] flex-1 flex-col px-5 pb-28 pt-8 md:max-w-[480px]">
        <div className="mb-6 flex items-center justify-between">
          <Link href="/" className="text-sm font-medium text-muted hover:text-ink">
            ← Storefront
          </Link>
          <Chip>Floor · Associate</Chip>
        </div>

        <Eyebrow>Return to value</Eyebrow>
        <Display as="h1" className="mt-3 text-[2rem]">
          Assess a return
        </Display>
        <Body className="mt-3">
          Photo → condition. Order history → risk. You confirm disposition — never
          auto-applied.
        </Body>

        <ol className="mt-8 flex gap-2" aria-label="Progress">
          {STEPS.map((label, i) => (
            <li
              key={label}
              className={cn(
                "flex-1 rounded-full px-2 py-2 text-center text-[11px] font-semibold uppercase tracking-[0.08em]",
                i <= stepIndex
                  ? "bg-ink text-paper"
                  : "bg-line/60 text-muted",
              )}
            >
              {i + 1}. {label}
            </li>
          ))}
        </ol>

        <form
          onSubmit={onAssess}
          className="mt-6 space-y-4 rounded-[20px] border border-line bg-paper p-5 shadow-elev-1"
        >
          <Input
            label="Order ID"
            value={orderId}
            onChange={(e) => setOrderId(e.target.value)}
            required
          />

          <div>
            <p className="mb-1.5 text-[13px] font-medium text-ink">Return photo</p>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="sr-only"
              onChange={onFile}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className={cn(
                "flex min-h-[200px] w-full flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-line bg-chalk/70 px-4 py-10 text-sm text-muted transition-colors hover:border-ink/25 hover:text-ink",
              )}
            >
              {preview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={preview}
                  alt="Return preview"
                  className="h-36 w-36 rounded-2xl object-cover shadow-elev-1"
                />
              ) : (
                <IconCamera size={28} />
              )}
              {preview ? "Change photo" : "Tap to capture or upload (max 4MB)"}
            </button>
          </div>

          <Button
            type="submit"
            fullWidth
            size="lg"
            isLoading={assess.isPending}
            disabled={!imageBase64 || !orderId.trim()}
          >
            Analyze return
          </Button>
        </form>

        {assess.isError ? (
          <p className="mt-4 text-sm text-coral" role="alert">
            Analysis failed. Try again.
          </p>
        ) : null}

        {assessment ? (
          <section className="mt-6 space-y-4 rounded-[20px] border border-line bg-paper p-5 shadow-elev-1">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl bg-amber-soft/80 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink/60">
                  Condition · from photo
                </p>
                <p className="mt-2 text-sm font-semibold capitalize text-ink">
                  {assessment.condition.replaceAll("_", " ")}
                </p>
                <p className="mt-2 text-[13px] leading-relaxed text-ink/75">
                  {assessment.condition_justification}
                </p>
              </div>
              <div className="rounded-2xl bg-coral-soft/70 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink/60">
                  Risk · from order history
                </p>
                <p className="mt-2 text-sm font-semibold capitalize text-ink">
                  {assessment.return_risk_tier}
                </p>
                <ul className="mt-2 list-inside list-disc text-[13px] text-ink/75">
                  {assessment.risk_factors.map((f) => (
                    <li key={f}>{f.replaceAll("_", " ")}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div>
              <label className="text-[13px] font-medium text-ink">
                Disposition — confirm to apply
              </label>
              <select
                className="mt-1.5 h-12 w-full rounded-xl border border-line bg-paper px-3 text-sm text-ink"
                value={disposition}
                onChange={(e) => setDisposition(e.target.value)}
              >
                {DISPOSITIONS.map((d) => (
                  <option key={d} value={d}>
                    {d.replaceAll("_", " ")}
                    {d === assessment.recommended_disposition
                      ? " · recommended"
                      : ""}
                  </option>
                ))}
              </select>
            </div>

            {confirmMsg ? (
              <p
                role="status"
                className="rounded-2xl border border-signal/25 bg-signal-soft px-4 py-3 text-sm text-ink"
              >
                {confirmMsg}
              </p>
            ) : null}
          </section>
        ) : null}
      </main>

      {assessment && !confirmMsg ? (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-paper/95 p-4 backdrop-blur-xl md:static md:border-0 md:bg-transparent md:p-0">
          <div className="mx-auto flex max-w-[440px] flex-col gap-2 sm:flex-row md:mt-4 md:max-w-[480px] md:px-5">
            <Button
              className="flex-1"
              size="lg"
              isLoading={confirm.isPending}
              onClick={() =>
                confirm.mutate({
                  assessment_id: assessment.assessment_id,
                  disposition,
                  override: disposition !== assessment.recommended_disposition,
                })
              }
            >
              Confirm disposition
            </Button>
            <Button
              className="flex-1"
              size="lg"
              variant="secondary"
              disabled={confirm.isPending}
              onClick={() =>
                confirm.mutate({
                  assessment_id: assessment.assessment_id,
                  disposition: "hold_for_review",
                  override: true,
                })
              }
            >
              Hold for review
            </Button>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

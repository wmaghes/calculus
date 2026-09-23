import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

export function Eyebrow({ className, ...props }: ComponentProps<"p">) {
  return <p className={cn("font-mono text-eyebrow uppercase text-fg-subtle", className)} {...props} />;
}

export function Container({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("mx-auto w-full max-w-6xl px-5 sm:px-8", className)} {...props} />;
}

/** Reading width for lesson text: never edge to edge. */
export function Prose({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cn("max-w-[66ch] space-y-4 text-[17px] leading-[1.7] text-fg-muted [&_strong]:text-fg", className)}
      {...props}
    />
  );
}

type BadgeTone = "neutral" | "accent" | "success" | "danger";

const tones: Record<BadgeTone, string> = {
  neutral: "border-line-strong bg-ink-800 text-fg-muted",
  accent: "border-accent-line bg-accent-soft text-accent",
  success: "border-success/30 bg-success-soft text-success",
  danger: "border-danger/30 bg-danger-soft text-danger",
};

export function Badge({ tone = "neutral", className, ...props }: ComponentProps<"span"> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

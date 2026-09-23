import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/cn";

const clamp = (n: number) => Math.min(100, Math.max(0, Math.round(n)));

type ProgressRingProps = {
  /** 0–100 */
  value: number;
  size?: number;
  stroke?: number;
  /** Replaces the default "NN%" in the centre. */
  children?: ReactNode;
  className?: string;
  label?: string;
};

// Fills from empty on first paint, then eases between values as progress
// changes (e.g. when a lesson completes without a page reload).
export function ProgressRing({ value, size = 88, stroke = 7, children, className, label }: ProgressRingProps) {
  const pct = clamp(value);
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - pct / 100);
  const done = pct === 100;

  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-label={label ?? "Progress"}
      className={cn("relative inline-grid shrink-0 place-items-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-ink-700" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={cn(
            "animate-ring stroke-accent transition-[stroke-dashoffset] duration-700 ease-out-soft",
            pct === 0 && "opacity-0",
            done && "drop-shadow-[0_0_6px_rgb(255_178_36/0.55)]",
          )}
          style={{ "--ring-circumference": circumference } as CSSProperties}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        {children ?? (
          <span
            className="font-display font-semibold tabular-nums tracking-tight text-fg"
            style={{ fontSize: Math.max(12, size * 0.22) }}
          >
            {pct}
            <span className="text-fg-subtle" style={{ fontSize: "0.6em" }}>
              %
            </span>
          </span>
        )}
      </div>
    </div>
  );
}

type ProgressBarProps = { value: number; className?: string; label?: string; size?: "sm" | "md" };

export function ProgressBar({ value, className, label, size = "sm" }: ProgressBarProps) {
  const pct = clamp(value);
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-label={label ?? "Progress"}
      className={cn("w-full overflow-hidden rounded-full bg-ink-700", size === "sm" ? "h-1.5" : "h-2.5", className)}
    >
      <div
        className="h-full origin-left animate-bar rounded-full bg-accent transition-[width] duration-700 ease-out-soft"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

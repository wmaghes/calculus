import { cn } from "@/lib/cn";

type CompleteCheckProps = {
  size?: number;
  /** Play the pop + draw animation. Use it at the moment of completion, not on every render. */
  animate?: boolean;
  className?: string;
};

// The "lesson complete" mark: an amber disc whose tick draws itself in.
export function CompleteCheck({ size = 20, animate = false, className }: CompleteCheckProps) {
  return (
    <span
      role="img"
      aria-label="Complete"
      className={cn(
        "inline-grid shrink-0 place-items-center rounded-full bg-accent text-accent-ink",
        animate && "animate-pop",
        className,
      )}
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 20 20" width={size * 0.62} height={size * 0.62} aria-hidden>
        <path
          d="M4.5 10.5l3.5 3.5 7.5-8"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.75}
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1}
          strokeDasharray={1}
          strokeDashoffset={animate ? 1 : 0}
          className={cn(animate && "animate-draw [animation-delay:140ms]")}
        />
      </svg>
    </span>
  );
}

// Lesson-list status marker: empty ring, amber-ringed current, or complete.
export function StatusDot({ status, size = 20 }: { status: "not_started" | "in_progress" | "complete"; size?: number }) {
  if (status === "complete") return <CompleteCheck size={size} />;
  return (
    <span
      aria-label={status === "in_progress" ? "In progress" : "Not started"}
      role="img"
      className={cn(
        "inline-block shrink-0 rounded-full border-2",
        status === "in_progress" ? "border-accent bg-accent-soft" : "border-ink-700",
      )}
      style={{ width: size, height: size }}
    />
  );
}

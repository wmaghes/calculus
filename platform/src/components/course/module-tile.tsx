import { CardLink } from "@/components/ui/card";
import { CompleteCheck } from "@/components/ui/complete-check";
import { Clock } from "@/components/ui/icons";
import { ProgressBar } from "@/components/ui/progress";
import { Badge } from "@/components/ui/typography";
import { cn } from "@/lib/cn";

type ModuleTileProps = {
  href: string;
  index: number;
  title: string;
  minutes: number;
  lessonCount: number;
  /** 0–100 */
  progress: number;
  current?: boolean;
};

export function ModuleTile({ href, index, title, minutes, lessonCount, progress, current }: ModuleTileProps) {
  const done = progress >= 100;
  return (
    <CardLink href={href} className={cn("flex flex-col gap-5", current && "border-accent-line")}>
      <div className="flex items-start justify-between gap-4">
        <span
          className={cn(
            "font-mono text-sm tabular-nums",
            current ? "text-accent" : "text-fg-subtle group-hover:text-fg-muted",
          )}
        >
          {String(index).padStart(2, "0")}
        </span>
        {done ? <CompleteCheck size={22} /> : current ? <Badge tone="accent">Up next</Badge> : null}
      </div>
      <h3 className="text-h3 font-semibold text-fg">{title}</h3>
      <div className="mt-auto space-y-3">
        <p className="flex items-center gap-1.5 text-[13px] text-fg-subtle">
          <Clock className="size-3.5" />
          {minutes} min · {lessonCount} lessons
        </p>
        <ProgressBar value={progress} label={`${title} progress`} />
      </div>
    </CardLink>
  );
}

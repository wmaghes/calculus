import { buttonClasses } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ArrowRight } from "@/components/ui/icons";
import { ProgressRing } from "@/components/ui/progress";
import { Eyebrow } from "@/components/ui/typography";
import Link from "next/link";

type TrackCardProps = {
  href: string;
  field: string;
  title: string;
  description?: string | null;
  modulesDone: number;
  modulesTotal: number;
  /** 0–100 */
  progress: number;
};

export function TrackCard({ href, field, title, description, modulesDone, modulesTotal, progress }: TrackCardProps) {
  const started = progress > 0;
  return (
    <Card className="flex flex-col gap-6 sm:flex-row sm:items-center">
      <ProgressRing value={progress} size={104} stroke={8} label={`${title} progress`} />
      <div className="min-w-0 flex-1 space-y-2">
        <Eyebrow>{field}</Eyebrow>
        <h3 className="text-h2 font-semibold text-fg">{title}</h3>
        {description && <p className="max-w-prose text-[15px] text-fg-muted">{description}</p>}
        <p className="text-[13px] tabular-nums text-fg-subtle">
          {modulesDone} of {modulesTotal} modules complete
        </p>
      </div>
      <Link href={href} className={buttonClasses({ variant: started ? "primary" : "secondary" })}>
        {started ? "Continue" : "Start track"}
        <ArrowRight className="size-4" />
      </Link>
    </Card>
  );
}

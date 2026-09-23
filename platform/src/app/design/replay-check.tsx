"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { CompleteCheck, StatusDot } from "@/components/ui/complete-check";
import { ProgressRing } from "@/components/ui/progress";

// Shows the moment of completion: ring fills to 100, check pops and draws.
export function CompletionDemo() {
  const [done, setDone] = useState(false);
  const [run, setRun] = useState(0);

  return (
    <div className="flex flex-wrap items-center gap-8">
      <ProgressRing value={done ? 100 : 75} size={96} stroke={8} label="Demo progress">
        {done ? <CompleteCheck key={run} size={36} animate /> : undefined}
      </ProgressRing>
      <div className="flex items-center gap-3">
        {done ? <CompleteCheck key={`inline-${run}`} size={24} animate /> : <StatusDot status="in_progress" size={24} />}
        <span className="text-[15px] text-fg-muted">{done ? "Lesson complete" : "Lesson in progress"}</span>
      </div>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => {
          setDone((d) => !d);
          setRun((r) => r + 1);
        }}
      >
        {done ? "Reset" : "Mark complete"}
      </Button>
    </div>
  );
}

import type { ReactNode } from "react";
import { Logo } from "@/components/brand/logo";
import { ProgressRing } from "@/components/ui/progress";
import { Eyebrow } from "@/components/ui/typography";
import { isSupabaseConfigured } from "@/lib/supabase/env";

const outcomes = [
  "How LLMs actually work, and where they fail",
  "Prompting that holds up on real finance questions",
  "Building and checking an AI workflow for your job",
];

export function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <main className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <section className="flex flex-col px-6 py-8 sm:px-12">
        <Logo />
        <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center py-12">
          <h1 className="text-h1 font-semibold text-fg">{title}</h1>
          <p className="mt-3 mb-10 text-[15px] text-fg-muted">{subtitle}</p>
          {isSupabaseConfigured ? (
            children
          ) : (
            <p className="rounded-lg border border-accent-line bg-accent-soft p-4 text-sm text-fg-muted">
              Supabase isn&apos;t configured yet. Copy <code className="font-mono text-fg">.env.example</code> to{" "}
              <code className="font-mono text-fg">.env.local</code> and add your project URL and publishable key.
            </p>
          )}
        </div>
      </section>

      <aside className="relative hidden overflow-hidden border-l border-line bg-ink-900 lg:flex lg:flex-col lg:justify-center lg:px-16">
        {/* soft amber bloom behind the ring */}
        <div className="pointer-events-none absolute -top-40 -right-40 size-[520px] rounded-full bg-accent/10 blur-[120px]" />
        <div className="relative max-w-md space-y-10">
          <ProgressRing value={72} size={132} stroke={10} label="Example progress">
            <span className="font-display text-h2 font-semibold tabular-nums">
              3<span className="text-fg-subtle">/4</span>
            </span>
          </ProgressRing>
          <div className="space-y-5">
            <Eyebrow>AI for Finance Professionals</Eyebrow>
            <p className="font-display text-h2 font-medium text-fg">
              Go from &ldquo;I use ChatGPT sometimes&rdquo; to shipping an AI workflow you can defend.
            </p>
          </div>
          <ul className="space-y-3">
            {outcomes.map((o) => (
              <li key={o} className="flex items-start gap-3 text-[15px] text-fg-muted">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
                {o}
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </main>
  );
}

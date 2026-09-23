import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ModuleTile } from "@/components/course/module-tile";
import { TrackCard } from "@/components/course/track-card";
import { AppNav, StreakChip } from "@/components/nav/app-nav";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusDot } from "@/components/ui/complete-check";
import { Field } from "@/components/ui/field";
import { ArrowRight, Play } from "@/components/ui/icons";
import { ProgressBar, ProgressRing } from "@/components/ui/progress";
import { Badge, Container, Eyebrow, Prose } from "@/components/ui/typography";
import { CompletionDemo } from "./replay-check";

export const metadata: Metadata = { title: "Design system" };

const swatches = [
  ["ink-950", "Page", "bg-ink-950"],
  ["ink-900", "Raised", "bg-ink-900"],
  ["ink-850", "Card", "bg-ink-850"],
  ["ink-800", "Hover / input", "bg-ink-800"],
  ["ink-700", "Track / border", "bg-ink-700"],
  ["accent", "CTA · progress · active", "bg-accent"],
  ["success", "Correct answer only", "bg-success"],
  ["danger", "Wrong answer only", "bg-danger"],
] as const;

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="grid gap-6 border-t border-line py-14 lg:grid-cols-[220px_1fr]">
      <div className="space-y-2">
        <h2 className="text-h3 font-semibold">{title}</h2>
        {note && <p className="text-[13px] leading-relaxed text-fg-subtle">{note}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

export default function DesignPage() {
  return (
    <>
      <AppNav user={{ name: "Priya Raman", email: "priya@northwind.example", role: "org_admin" }} streak={4} />
      <Container className="pb-24">
        <header className="py-16">
          <Eyebrow>Stage 1 · Design system</Eyebrow>
          <h1 className="mt-4 text-h1 font-semibold sm:text-display">Components</h1>
          <p className="mt-4 max-w-xl text-lg text-fg-muted">
            Near-black base, one amber accent, strong type contrast. Tailwind&apos;s default palette is switched off,
            so these tokens are the only colors available.
          </p>
        </header>

        <Section title="Color" note="Amber appears only on CTAs, progress and active states. Green and red are reserved for answer feedback.">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {swatches.map(([token, use, cls]) => (
              <div key={token} className="overflow-hidden rounded-md border border-line">
                <div className={`h-16 ${cls}`} />
                <div className="space-y-0.5 bg-ink-900 px-3 py-2.5">
                  <p className="font-mono text-xs text-fg">{token}</p>
                  <p className="text-xs text-fg-subtle">{use}</p>
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Type" note="Inter Tight for display, Inter for reading, JetBrains Mono for tokens and labels.">
          <div className="space-y-6">
            <p className="font-display text-display font-semibold">Tokens, not words.</p>
            <p className="text-h1 font-semibold">What an LLM actually is</p>
            <p className="text-h2 font-semibold">Why hallucination happens</p>
            <p className="text-h3 font-semibold">Lesson 1.2 · Prompt sensitivity</p>
            <Eyebrow>Eyebrow · module 01</Eyebrow>
            <Prose>
              <p>
                A language model predicts the next <strong>token</strong>, a chunk of text a few characters long,
                over and over. It has no lookup table of facts. When the most likely continuation is wrong, it is
                wrong with the same fluency as when it is right.
              </p>
            </Prose>
          </div>
        </Section>

        <Section title="Buttons">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-3">
              <Button>Continue lesson</Button>
              <Button variant="secondary">Ask the tutor</Button>
              <Button variant="ghost">Skip for now</Button>
              <Button loading>Grading…</Button>
              <Button disabled>Disabled</Button>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm">Small</Button>
              <Button size="md">Medium</Button>
              <ButtonLink href="#" size="lg">
                <Play className="size-4" />
                Start module
                <ArrowRight className="size-4" />
              </ButtonLink>
            </div>
          </div>
        </Section>

        <Section title="Badges & status">
          <div className="flex flex-wrap items-center gap-3">
            <Badge>Walkthrough</Badge>
            <Badge tone="accent">Up next</Badge>
            <Badge tone="success">Correct</Badge>
            <Badge tone="danger">Not quite</Badge>
            <StreakChip days={4} />
            <StreakChip days={0} />
            <span className="flex items-center gap-2 pl-2">
              <StatusDot status="not_started" />
              <StatusDot status="in_progress" />
              <StatusDot status="complete" />
            </span>
          </div>
        </Section>

        <Section title="Progress" note="Rings fill from empty on load and ease between values when progress changes.">
          <div className="space-y-10">
            <div className="flex flex-wrap items-end gap-8">
              <ProgressRing value={0} size={72} stroke={6} />
              <ProgressRing value={35} size={88} />
              <ProgressRing value={72} size={104} stroke={8} />
              <ProgressRing value={100} size={120} stroke={9} />
            </div>
            <div className="max-w-md space-y-4">
              <ProgressBar value={20} />
              <ProgressBar value={64} />
              <ProgressBar value={100} size="md" />
            </div>
            <CompletionDemo />
          </div>
        </Section>

        <Section title="Form fields">
          <div className="grid max-w-md gap-4">
            <Field label="Work email" placeholder="you@company.com" type="email" />
            <Field label="Password" type="password" hint="At least 8 characters." />
            <Field label="Company" defaultValue="Northwind" error="That workspace name is taken." />
          </div>
        </Section>

        <Section title="Cards" note="Interactive cards lift 2px, brighten the border, and show an amber hairline on hover.">
          <div className="space-y-6">
            <TrackCard
              href="#"
              field="Finance"
              title="AI for Finance Professionals"
              description="From “I use ChatGPT sometimes” to building and evaluating an AI workflow for your job."
              modulesDone={2}
              modulesTotal={6}
              progress={38}
            />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <ModuleTile href="#" index={1} title="What an LLM actually is (and isn’t)" minutes={14} lessonCount={4} progress={100} />
              <ModuleTile href="#" index={2} title="Prompting for precision" minutes={12} lessonCount={5} progress={40} current />
              <ModuleTile href="#" index={3} title="Checking AI output against the numbers" minutes={15} lessonCount={4} progress={0} />
            </div>
            <Card>
              <p className="text-[15px] text-fg-muted">A plain, static card for content that isn&apos;t a link.</p>
            </Card>
          </div>
        </Section>

        <Section title="Navigation" note="Sticky, blurred top bar. The active link gets a short amber underline. Shown at the top of this page, as an org admin.">
          <p className="text-[15px] text-fg-muted">
            Contents: logo, primary links, streak chip and account menu (click the initials). Admins get a Team link once the admin dashboard exists in Stage 5. The lesson
            sidebar arrives with the module page in Stage 2.
          </p>
        </Section>
      </Container>
    </>
  );
}

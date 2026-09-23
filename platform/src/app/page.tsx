import { Logo } from "@/components/brand/logo";
import { ButtonLink } from "@/components/ui/button";
import { ArrowRight } from "@/components/ui/icons";
import { Container, Eyebrow } from "@/components/ui/typography";
import { BRAND } from "@/lib/brand";

// Placeholder front door. The full landing page (pricing, social proof,
// free preview) is not in the staged plan yet.
export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <Container className="flex h-16 items-center justify-between">
        <Logo />
        <div className="flex items-center gap-2">
          <ButtonLink href="/login" variant="ghost" size="sm">
            Sign in
          </ButtonLink>
          <ButtonLink href="/signup" size="sm">
            Get started
          </ButtonLink>
        </div>
      </Container>
      <Container className="flex flex-1 flex-col justify-center py-24">
        <Eyebrow className="animate-rise">AI literacy · Finance track</Eyebrow>
        <h1 className="mt-6 max-w-4xl animate-rise text-[2.75rem] leading-[1.04] font-semibold tracking-[-0.035em] [animation-delay:60ms] sm:text-display">
          {BRAND.tagline}
        </h1>
        <p className="mt-6 max-w-xl animate-rise text-lg text-fg-muted [animation-delay:120ms]">
          Short, hands-on modules that take finance teams from casual chatbot use to building and checking AI
          workflows they can trust, with an AI tutor on every lesson.
        </p>
        <div className="mt-10 flex animate-rise flex-wrap gap-3 [animation-delay:180ms]">
          <ButtonLink href="/signup" size="lg">
            Start the free module
            <ArrowRight className="size-4" />
          </ButtonLink>
          <ButtonLink href="/design" size="lg" variant="secondary">
            View design system
          </ButtonLink>
        </div>
      </Container>
    </div>
  );
}

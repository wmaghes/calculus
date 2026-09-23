import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { cn } from "@/lib/cn";

// The mark is a three-quarter progress ring: the product's core promise,
// finishing what you start.
export function LogoMark({ size = 24, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden className={className}>
      <circle cx="12" cy="12" r="9" fill="none" strokeWidth="3.5" className="stroke-ink-700" />
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeDasharray={`${2 * Math.PI * 9 * 0.72} 999`}
        transform="rotate(-90 12 12)"
        className="stroke-accent"
      />
      <circle cx="12" cy="12" r="2.5" className="fill-fg" />
    </svg>
  );
}

export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-2.5", className)} aria-label={`${BRAND.name} home`}>
      <LogoMark />
      <span className="font-display text-[17px] font-semibold tracking-tight text-fg">{BRAND.name}</span>
    </Link>
  );
}

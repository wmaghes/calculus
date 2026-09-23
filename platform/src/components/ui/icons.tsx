import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

export function ArrowRight(props: IconProps) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden {...stroke} {...props}>
      <path d="M4 10h12M11 5l5 5-5 5" />
    </svg>
  );
}

export function Check(props: IconProps) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden {...stroke} strokeWidth={2.25} {...props}>
      <path d="M4.5 10.5l3.5 3.5 7.5-8" />
    </svg>
  );
}

export function Flame(props: IconProps) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden {...stroke} {...props}>
      <path d="M10 2.5c.5 2.6 4.5 4.8 4.5 9a4.5 4.5 0 01-9 0c0-1.7.8-3 1.9-4 .2 1.3.8 2.1 1.6 2.5C9 7.6 8.6 5 10 2.5z" />
    </svg>
  );
}

export function Play(props: IconProps) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden fill="currentColor" {...props}>
      <path d="M6.5 4.6v10.8a.6.6 0 00.9.5l8.4-5.4a.6.6 0 000-1L7.4 4.1a.6.6 0 00-.9.5z" />
    </svg>
  );
}

export function Clock(props: IconProps) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden {...stroke} {...props}>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 6.5V10l2.5 1.5" />
    </svg>
  );
}

export function Spinner(props: IconProps) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden className="animate-spin" {...props}>
      <circle cx="10" cy="10" r="7.5" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2.5" />
      <path d="M17.5 10A7.5 7.5 0 0010 2.5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export function GoogleMark(props: IconProps) {
  return (
    <svg viewBox="0 0 18 18" aria-hidden {...props}>
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 01-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 009 18z" />
      <path fill="#FBBC05" d="M3.97 10.72a5.4 5.4 0 010-3.44V4.95H.96a9 9 0 000 8.1l3.01-2.33z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 00.96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" />
    </svg>
  );
}

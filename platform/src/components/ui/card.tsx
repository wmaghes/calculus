import Link from "next/link";
import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

const surface = "relative rounded-lg border border-line bg-ink-850 shadow-card";

// Hover: border brightens, the card lifts 2px, and an amber hairline fades in
// along the top edge.
const interactive =
  "group transition-[transform,border-color,background-color] duration-200 ease-out-soft " +
  "hover:-translate-y-0.5 hover:border-line-strong hover:bg-ink-800 " +
  "before:pointer-events-none before:absolute before:inset-x-6 before:top-0 before:h-px " +
  "before:bg-linear-to-r before:from-transparent before:via-accent before:to-transparent " +
  "before:opacity-0 before:transition-opacity before:duration-200 hover:before:opacity-70";

type CardProps = ComponentProps<"div"> & { padded?: boolean };

export function Card({ className, padded = true, ...props }: CardProps) {
  return <div className={cn(surface, padded && "p-6", className)} {...props} />;
}

type CardLinkProps = ComponentProps<typeof Link> & { padded?: boolean };

export function CardLink({ className, padded = true, ...props }: CardLinkProps) {
  return <Link className={cn(surface, interactive, "block", padded && "p-6", className)} {...props} />;
}

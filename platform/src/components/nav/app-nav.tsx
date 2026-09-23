import { signOut } from "@/app/(auth)/actions";
import { Logo } from "@/components/brand/logo";
import { Flame } from "@/components/ui/icons";
import { Container } from "@/components/ui/typography";
import type { Enums } from "@/lib/database.types";
import { cn } from "@/lib/cn";
import { NavLinks } from "./nav-links";

export type NavUser = { name: string | null; email: string; role: Enums<"user_role"> };

export function AppNav({ user, streak = 0 }: { user: NavUser; streak?: number }) {
  const links = [{ href: "/dashboard", label: "Dashboard" }];
  // Stage 5: add { href: "/admin", label: "Team" } for org admins.

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-ink-950/80 backdrop-blur-xl">
      <Container className="flex h-16 items-center gap-8">
        <Logo href="/dashboard" />
        <NavLinks links={links} />
        <div className="ml-auto flex items-center gap-3">
          <StreakChip days={streak} />
          <UserMenu user={user} />
        </div>
      </Container>
    </header>
  );
}

export function StreakChip({ days }: { days: number }) {
  const active = days > 0;
  return (
    <span
      title={active ? `${days}-day streak` : "Complete a lesson today to start a streak"}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium tabular-nums",
        active ? "border-accent-line bg-accent-soft text-accent" : "border-line-strong text-fg-subtle",
      )}
    >
      <Flame className="size-4" />
      {days}
      <span className="sr-only">day streak</span>
    </span>
  );
}

function initials(name: string | null, email: string) {
  const source = name?.trim() || email;
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return (parts[0]?.[0] ?? "?").concat(parts[1]?.[0] ?? "").toUpperCase();
}

function UserMenu({ user }: { user: NavUser }) {
  return (
    <details className="group relative">
      <summary
        className="grid size-8 cursor-pointer list-none place-items-center rounded-full border border-line-strong bg-ink-800 text-xs font-semibold text-fg transition-colors hover:border-fg-subtle/50 [&::-webkit-details-marker]:hidden"
        aria-label="Account menu"
      >
        {initials(user.name, user.email)}
      </summary>
      <div className="absolute right-0 mt-2 w-60 animate-rise rounded-lg border border-line-strong bg-ink-900 p-1.5 shadow-card">
        <div className="px-3 py-2.5">
          <p className="truncate text-sm font-medium text-fg">{user.name ?? "Your account"}</p>
          <p className="truncate text-[13px] text-fg-subtle">{user.email}</p>
        </div>
        <div className="my-1 h-px bg-line" />
        <form action={signOut}>
          <button className="w-full rounded-md px-3 py-2 text-left text-sm text-fg-muted transition-colors hover:bg-ink-800 hover:text-fg">
            Sign out
          </button>
        </form>
      </div>
    </details>
  );
}

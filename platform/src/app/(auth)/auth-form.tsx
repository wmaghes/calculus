"use client";

import Link from "next/link";
import { useActionState } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { GoogleMark } from "@/components/ui/icons";
import { signInWithGoogle, signInWithPassword, signUpWithPassword, type AuthState } from "./actions";

type Mode = "login" | "signup";

export function AuthForm({ mode, next, initialError }: { mode: Mode; next?: string; initialError?: string }) {
  const action = mode === "login" ? signInWithPassword : signUpWithPassword;
  const [state, formAction, pending] = useActionState<AuthState, FormData>(action, { error: initialError });

  if (state.notice) {
    return (
      <div role="status" className="animate-rise space-y-3 rounded-lg border border-accent-line bg-accent-soft p-5">
        <p className="font-medium text-fg">Almost there</p>
        <p className="text-[15px] text-fg-muted">{state.notice}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <form action={signInWithGoogle}>
        <input type="hidden" name="next" value={next ?? ""} />
        <Button type="submit" variant="secondary" size="lg" className="w-full">
          <GoogleMark className="size-[18px]" />
          Continue with Google
        </Button>
      </form>

      <div className="flex items-center gap-3 text-[13px] text-fg-subtle">
        <span className="h-px flex-1 bg-line" />
        or with email
        <span className="h-px flex-1 bg-line" />
      </div>

      <form action={formAction} className="space-y-4" noValidate>
        <input type="hidden" name="next" value={next ?? ""} />
        {mode === "signup" && <Field label="Full name" name="name" autoComplete="name" required />}
        <Field
          label="Work email"
          name="email"
          type="email"
          autoComplete="email"
          defaultValue={state.email}
          required
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          hint={mode === "signup" ? "At least 8 characters." : undefined}
          required
        />
        {state.error && (
          <p role="alert" className="rounded-md border border-danger/30 bg-danger-soft px-3.5 py-2.5 text-sm text-danger">
            {state.error}
          </p>
        )}
        <Button type="submit" size="lg" className="w-full" loading={pending}>
          {mode === "login" ? "Sign in" : "Create account"}
        </Button>
      </form>

      <p className="text-center text-sm text-fg-subtle">
        {mode === "login" ? "New here? " : "Already have an account? "}
        <Link
          href={{ pathname: mode === "login" ? "/signup" : "/login", query: next ? { next } : undefined }}
          className="font-medium text-fg underline decoration-line-strong underline-offset-4 hover:decoration-accent"
        >
          {mode === "login" ? "Create an account" : "Sign in"}
        </Link>
      </p>
    </div>
  );
}

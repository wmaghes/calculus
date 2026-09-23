import type { Metadata } from "next";
import { AuthForm } from "../auth-form";
import { AuthShell } from "../auth-shell";

export const metadata: Metadata = { title: "Sign in" };

const errors: Record<string, string> = {
  google: "Google sign-in didn't start. Try again.",
  callback: "That sign-in link didn't work. It may have expired.",
  link: "That confirmation link is invalid or has expired.",
};

export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const { next, error } = await searchParams;
  return (
    <AuthShell title="Welcome back" subtitle="Pick up where you left off.">
      <AuthForm
        mode="login"
        next={typeof next === "string" ? next : undefined}
        initialError={typeof error === "string" ? errors[error] : undefined}
      />
    </AuthShell>
  );
}

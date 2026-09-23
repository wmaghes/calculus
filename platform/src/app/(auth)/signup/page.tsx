import type { Metadata } from "next";
import { AuthForm } from "../auth-form";
import { AuthShell } from "../auth-shell";

export const metadata: Metadata = { title: "Create your account" };

export default async function SignupPage({ searchParams }: PageProps<"/signup">) {
  const { next } = await searchParams;
  return (
    <AuthShell title="Start learning" subtitle="Ten-minute modules. Real exercises. No filler.">
      <AuthForm mode="signup" next={typeof next === "string" ? next : undefined} />
    </AuthShell>
  );
}

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { cache } from "react";
import type { Database, Tables } from "@/lib/database.types";
import { isSupabaseConfigured, SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "./env";

// A Supabase client acting as the signed-in user, so every query is filtered
// by RLS. Create one per request; never share it across requests.
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient<Database>(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
        } catch {
          // Server Components cannot set cookies. The proxy refreshes the
          // session on every request, so this is safe to ignore here.
        }
      },
    },
  });
}

export type Viewer = {
  id: string;
  email: string;
  profile: Tables<"users">;
  organization: Tables<"organizations">;
};

// The signed-in user with their profile and organization, or null.
// Cached per request so layouts and pages can both call it.
export const getViewer = cache(async (): Promise<Viewer | null> => {
  if (!isSupabaseConfigured) return null;
  const supabase = await createClient();
  const { data: claims } = await supabase.auth.getClaims();
  const userId = claims?.claims.sub;
  if (!userId) return null;

  const { data: profile } = await supabase
    .from("users")
    .select("*, organization:organizations(*)")
    .eq("id", userId)
    .single();
  // Signed in but no profile means the signup trigger never ran. Returning
  // null here would bounce between /login and /dashboard, so fail loudly.
  if (!profile?.organization) {
    throw new Error("Signed-in user has no profile row. Is the foundation migration applied?");
  }

  const { organization, ...rest } = profile;
  return { id: userId, email: rest.email, profile: rest, organization };
});

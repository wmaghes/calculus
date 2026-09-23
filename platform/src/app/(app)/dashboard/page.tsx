import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { TrackCard } from "@/components/course/track-card";
import { Card } from "@/components/ui/card";
import { Badge, Container, Eyebrow } from "@/components/ui/typography";
import { createClient, getViewer } from "@/lib/supabase/server";

export const metadata: Metadata = { title: "Dashboard" };

const planLabel = { individual: "Individual", team: "Team", enterprise: "Enterprise" } as const;
const roleLabel = { learner: "Learner", org_admin: "Admin", super_admin: "Super admin" } as const;

// Stage 1 placeholder: proves auth, the org link and RLS-scoped reads work.
// Stage 2 replaces this with the real dashboard (continue, streak, next up).
export default async function DashboardPage() {
  const viewer = await getViewer();
  if (!viewer) redirect("/login");

  const supabase = await createClient();
  const { data: tracks } = await supabase
    .from("tracks")
    .select("id, title, description, target_field, modules(count)")
    .order("created_at");

  const firstName = viewer.profile.name?.split(" ")[0];

  return (
    <Container className="space-y-12 py-12">
      <header className="space-y-3">
        <Eyebrow>{viewer.organization.name}</Eyebrow>
        <h1 className="text-h1 font-semibold">{firstName ? `Welcome, ${firstName}.` : "Welcome."}</h1>
        <div className="flex flex-wrap gap-2">
          <Badge>{planLabel[viewer.organization.plan_type]} plan</Badge>
          <Badge>{roleLabel[viewer.profile.role]}</Badge>
        </div>
      </header>

      <section className="space-y-4">
        <h2 className="text-h3 font-semibold text-fg-muted">Your tracks</h2>
        {tracks && tracks.length > 0 ? (
          tracks.map((t) => (
            <TrackCard
              key={t.id}
              href={`/tracks/${t.id}`}
              field={t.target_field}
              title={t.title}
              description={t.description}
              modulesDone={0}
              modulesTotal={t.modules[0]?.count ?? 0}
              progress={0}
            />
          ))
        ) : (
          <Card className="text-[15px] text-fg-muted">
            No tracks yet. The pilot track arrives in Stage 4; until then you can add one in the Supabase table editor.
          </Card>
        )}
      </section>
    </Container>
  );
}

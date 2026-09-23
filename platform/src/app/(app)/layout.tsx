import { redirect } from "next/navigation";
import { AppNav } from "@/components/nav/app-nav";
import { getViewer } from "@/lib/supabase/server";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const viewer = await getViewer();
  if (!viewer) redirect("/login");

  return (
    <>
      <AppNav user={viewer.profile} />
      {children}
    </>
  );
}

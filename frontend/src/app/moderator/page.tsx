import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { ModeratorPanel } from "@/components/moderator/ModeratorPanel";

export const metadata: Metadata = { title: "Panel moderatora" };

export default function ModeratorPage() {
  return (
    <PageShell
      wide
      title="Panel moderatora"
      lead="Sprawy przekazane do sprawdzenia przez człowieka, statystyki i zdarzenia bezpieczeństwa."
    >
      <ModeratorPanel />
    </PageShell>
  );
}

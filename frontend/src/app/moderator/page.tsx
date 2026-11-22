import type { Metadata } from "next";
import { BackButton } from "@/components/layout/BackButton";
import { PageShell } from "@/components/layout/PageShell";
import { ModeratorPanel } from "@/components/moderator/ModeratorPanel";

export const metadata: Metadata = { title: "Panel moderatora" };

export default function ModeratorPage() {
  return (
    <PageShell
      wide
      title="Panel moderatora"
      lead="Twierdzenia przekazane do analizy przez człowieka, statystyki i zdarzenia bezpieczeństwa."
      headerAside={<div id="moderator-account-slot" />}
    >
      <BackButton label="Wróć do analizy" />
      <div className="mt-4">
        <ModeratorPanel />
      </div>
    </PageShell>
  );
}

import type { Metadata } from "next";
import { PublicEventMap } from "@/components/events/PublicEventMap";
import { PageShell } from "@/components/layout/PageShell";

export const metadata: Metadata = { title: "Mapa wydarzeń" };

export default function EventMapPage() {
  return (
    <PageShell
      wide
      title="Mapa wydarzeń"
      lead="Zagregowany obraz tematów, które obywatele zgłaszają do sprawdzenia. Wydarzenia są łączone na podstawie podobieństwa treści, czasu i wspólnych źródeł. To kontekst, a nie werdykt."
    >
      <PublicEventMap />
    </PageShell>
  );
}

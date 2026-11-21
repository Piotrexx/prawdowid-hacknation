import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { SourceCatalog } from "@/components/sources/SourceCatalog";

export const metadata: Metadata = { title: "Katalog źródeł" };

export default function SourcesPage() {
  return (
    <PageShell
      wide
      title="Katalog źródeł"
      lead="Prawdowid odpowiada tylko na podstawie tych źródeł. Tutaj sprawdzisz, skąd pochodzą materiały i według jakich zasad je wybrano."
    >
      <SourceCatalog />
    </PageShell>
  );
}

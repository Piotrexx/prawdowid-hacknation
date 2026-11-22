import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { SourceCatalog } from "@/components/sources/SourceCatalog";

export const metadata: Metadata = {
  title: "Katalog źródeł – Prawdowid",
  description:
    "Sprawdź, z jakich źródeł korzysta Prawdowid: instytucje publiczne, redakcje fact-checkingowe i media.",
};

export default function SourcesPage() {
  return (
    <PageShell
      wide
      title="Katalog źródeł"
      lead="Prawdowid odpowiada tylko na podstawie tych źródeł. Filtruj je po kategorii i sprawdź, skąd pochodzą materiały oraz jaką mają wagę w ocenie dowodów."
    >
      <SourceCatalog />
    </PageShell>
  );
}

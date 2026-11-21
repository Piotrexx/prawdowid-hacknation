import type { Metadata } from "next";
import { AboutContent } from "@/components/about/AboutContent";
import { PageShell } from "@/components/layout/PageShell";

export const metadata: Metadata = { title: "Jak to działa" };

export default function AboutPage() {
  return (
    <PageShell
      title="Jak to działa"
      lead="Prawdowid pomaga sprawdzić, czy informacja ma oparcie w źródłach. Poniżej znajdziesz proste wyjaśnienie, co robi, a czego nie robi."
    >
      <AboutContent />
    </PageShell>
  );
}

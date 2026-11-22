import type { Metadata } from "next";

interface PageProps {
  params: Promise<{ id: string }>;
}
import { Suspense } from "react";
import { PermalinkView } from "@/components/check/PermalinkView";
import { LoadingBlock } from "@/components/ui/LoadState";

export const metadata: Metadata = { title: "Wynik analizy" };

export default function CheckPage({ params }: PageProps) {
  return (
    <Suspense
      fallback={
        <div className="px-5 py-8 sm:p-10">
          <LoadingBlock label="Wczytuję wynik analizy…" />
        </div>
      }
    >
      {params.then(({ id }) => (
        <PermalinkView id={id} />
      ))}
    </Suspense>
  );
}

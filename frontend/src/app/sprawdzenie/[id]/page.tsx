import type { Metadata } from "next";
import type { ReactNode } from "react";

interface PageProps {
  params: Promise<{ id: string }>;
}
import { Suspense } from "react";
import { PermalinkView } from "@/components/check/PermalinkView";
import { LoadingBlock } from "@/components/ui/LoadState";

export const metadata: Metadata = { title: "Wynik sprawdzenia" };

export default function CheckPage({ params }: PageProps) {
  return (
    <Suspense
      fallback={
        <div className="px-5 py-8 sm:p-10">
          <LoadingBlock label="Wczytuję wynik sprawdzenia…" />
        </div>
      }
    >
      {params.then(({ id }) => (
        <PermalinkView id={id} />
      ))}
    </Suspense>
  );
}

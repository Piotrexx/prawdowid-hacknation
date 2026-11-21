import type { Metadata } from "next";
import { Suspense } from "react";
import { PermalinkView } from "@/components/check/PermalinkView";
import { PageShell } from "@/components/layout/PageShell";
import { LoadingBlock } from "@/components/ui/LoadState";

export const metadata: Metadata = { title: "Zapisane sprawdzenie" };

export default function CheckPage({ params }: PageProps<"/sprawdzenie/[id]">) {
  return (
    <PageShell title="Zapisane sprawdzenie">
      <Suspense fallback={<LoadingBlock label="Wczytuję wynik sprawdzenia…" />}>
        {params.then(({ id }) => (
          <PermalinkView id={id} />
        ))}
      </Suspense>
    </PageShell>
  );
}

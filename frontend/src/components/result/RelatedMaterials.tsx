import { useId } from "react";
import type { SourceRef } from "@/lib/types";
import { SourceMeta } from "./SourceMeta";

export function RelatedMaterials({ materials }: { materials: SourceRef[] }) {
  const headingId = useId();
  if (materials.length === 0) return null;

  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId} className="text-xl font-semibold">
        Materiały, które mogą pomóc – oceń je samodzielnie
      </h3>
      <p className="mt-1 text-muted">
        System ich nie ocenił. To tylko lista materiałów znalezionych w źródłach.
      </p>
      <ul className="mt-4 space-y-3">
        {materials.map((source) => (
          <li
            key={source.doc_id}
            className="rounded-lg border border-line bg-surface px-4 py-3"
          >
            <SourceMeta source={source} />
          </li>
        ))}
      </ul>
    </section>
  );
}

import type { SourceRef } from "@/lib/types";
import { SourceMeta } from "./SourceMeta";

interface RelatedMaterialsProps {
  materials: SourceRef[];
  id: string;
  level?: 2 | 3;
}

export function RelatedMaterials({ materials, id, level = 3 }: RelatedMaterialsProps) {
  if (materials.length === 0) return null;
  const Heading = level === 2 ? "h2" : "h3";

  return (
    <section id={id} aria-labelledby={`${id}-tytul`} className="scroll-mt-6 bg-subtle px-6 py-7">
      <Heading id={`${id}-tytul`} className="text-xl font-semibold">
        Materiały, które mogą pomóc – oceń je samodzielnie
      </Heading>
      <p className="mt-1 mb-4.5 text-sm text-muted">
        System ich nie ocenił. To tylko lista materiałów znalezionych w źródłach.
      </p>
      <ul className="flex flex-col gap-2">
        {materials.map((source) => (
          <li key={source.doc_id} className="border border-line bg-surface px-4.5 py-3.5">
            <SourceMeta source={source} />
          </li>
        ))}
      </ul>
    </section>
  );
}

import { ExternalLink } from "@/components/ui/ExternalLink";
import { Tag } from "@/components/ui/Tag";
import { formatDate, formatInteger } from "@/lib/format";
import { SOURCE_TYPE_LABELS, STORAGE_LABELS } from "@/lib/labels";
import type { SourceCatalogEntry } from "@/lib/types";

export function SourceCard({ source }: { source: SourceCatalogEntry }) {
  const details: Array<[string, string]> = [
    ["Licencja", source.license || "brak danych"],
    ["Co przechowujemy", STORAGE_LABELS[source.storage] ?? source.storage],
    ["Dlaczego to źródło", source.qualification || "brak danych"],
    ["Aktualizacja", source.update_policy || "brak danych"],
    ["Liczba dokumentów", formatInteger(source.documents)],
    ["Najnowszy materiał", formatDate(source.newest) ?? "brak daty"],
  ];

  return (
    <li className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <h3 className="text-lg font-semibold">
        <ExternalLink href={source.homepage} className="inline-block py-2">
          {source.name}
        </ExternalLink>
      </h3>
      <p className="text-muted">{source.publisher}</p>

      <p className="mt-2 flex flex-wrap gap-1.5">
        <Tag>{SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type}</Tag>
        <Tag>Poziom {source.tier}</Tag>
      </p>

      <dl className="mt-3 space-y-1.5">
        {details.map(([label, value]) => (
          <div key={label} className="sm:grid sm:grid-cols-[11rem_1fr] sm:gap-3">
            <dt className="text-muted">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </li>
  );
}

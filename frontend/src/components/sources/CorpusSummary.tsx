import { StatTile } from "@/components/ui/StatTile";
import { formatDateTime, formatInteger } from "@/lib/format";
import { SOURCE_TYPE_LABELS, labelFor } from "@/lib/labels";
import type { CorpusStats } from "@/lib/types";

export function CorpusSummary({ corpus }: { corpus: CorpusStats }) {
  const byType = Object.entries(corpus.by_type).sort(([, a], [, b]) => b - a);

  return (
    <section aria-labelledby="zbior-w-liczbach">
      <h2 id="zbior-w-liczbach" className="text-2xl font-semibold">
        Zbiór źródeł w liczbach
      </h2>
      <dl className="mt-4 grid gap-3 sm:grid-cols-3">
        <StatTile label="Dokumenty" value={formatInteger(corpus.documents)} />
        <StatTile
          label="Fragmenty"
          value={formatInteger(corpus.passages)}
          hint="Części dokumentów, w których system szuka cytatów."
        />
        <StatTile label="Domeny" value={formatInteger(corpus.domains)} />
      </dl>

      {byType.length > 0 ? (
        <>
          <h3 className="mt-6 font-semibold">Dokumenty według rodzaju źródła</h3>
          <ul className="mt-2 grid gap-x-8 gap-y-1 sm:grid-cols-2">
            {byType.map(([type, count]) => (
              <li
                key={type}
                className="flex justify-between gap-4 border-b border-line py-1.5"
              >
                <span>{labelFor(SOURCE_TYPE_LABELS, type)}</span>
                <span className="font-medium tabular-nums">{formatInteger(count)}</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <p className="mt-4 text-muted">
        Wersja zbioru: {corpus.version || "brak danych"}. Zbudowano:{" "}
        {formatDateTime(corpus.built_at) ?? "brak danych"}.
      </p>
    </section>
  );
}

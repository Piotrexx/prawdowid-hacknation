"use client";

import { useState } from "react";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { getSources } from "@/lib/api";
import { plural } from "@/lib/format";
import { SOURCE_TYPES, SOURCE_TYPE_LABELS } from "@/lib/labels";
import type { SourceCatalogEntry, SourceType } from "@/lib/types";
import { useLoad } from "@/lib/useLoad";
import { CorpusSummary } from "./CorpusSummary";
import { SourceCard } from "./SourceCard";

type EnabledFilter = "all" | "enabled" | "disabled";

const FIELD_CLASS =
  "mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3";

function matches(
  source: SourceCatalogEntry,
  type: SourceType | "all",
  enabled: EnabledFilter,
  query: string,
): boolean {
  if (type !== "all" && source.source_type !== type) return false;
  if (enabled === "enabled" && !source.enabled) return false;
  if (enabled === "disabled" && source.enabled) return false;
  if (!query) return true;
  const haystack = [source.name, source.publisher, source.qualification, source.homepage]
    .join(" ")
    .toLocaleLowerCase("pl");
  return haystack.includes(query);
}

function SourceList({ sources }: { sources: SourceCatalogEntry[] }) {
  const [type, setType] = useState<SourceType | "all">("all");
  const [enabled, setEnabled] = useState<EnabledFilter>("all");
  const [search, setSearch] = useState("");

  const query = search.trim().toLocaleLowerCase("pl");
  const visible = sources.filter((source) => matches(source, type, enabled, query));

  return (
    <section aria-labelledby="lista-zrodel">
      <h2 id="lista-zrodel" className="text-2xl font-semibold">
        Lista źródeł
      </h2>

      <form
        role="search"
        aria-label="Filtrowanie listy źródeł"
        className="mt-4 grid gap-4 sm:grid-cols-3"
        onSubmit={(event) => event.preventDefault()}
      >
        <label className="block font-medium">
          Szukaj
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Nazwa lub wydawca"
            className={`${FIELD_CLASS} placeholder:text-muted`}
          />
        </label>
        <label className="block font-medium">
          Rodzaj źródła
          <select
            value={type}
            onChange={(event) => setType(event.target.value as SourceType | "all")}
            className={FIELD_CLASS}
          >
            <option value="all">Wszystkie rodzaje</option>
            {SOURCE_TYPES.map((value) => (
              <option key={value} value={value}>
                {SOURCE_TYPE_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
        <label className="block font-medium">
          Stan
          <select
            value={enabled}
            onChange={(event) => setEnabled(event.target.value as EnabledFilter)}
            className={FIELD_CLASS}
          >
            <option value="all">Włączone i wyłączone</option>
            <option value="enabled">Tylko włączone</option>
            <option value="disabled">Tylko wyłączone</option>
          </select>
        </label>
      </form>

      <p role="status" className="mt-4 text-muted">
        Pokazuję {visible.length} z {sources.length}{" "}
        {plural(sources.length, "źródła", "źródeł", "źródeł")}.
      </p>

      {visible.length > 0 ? (
        <ul className="mt-3 grid gap-4 lg:grid-cols-2">
          {visible.map((source) => (
            <SourceCard key={source.id} source={source} />
          ))}
        </ul>
      ) : (
        <p className="mt-3 rounded-lg border border-dashed border-line-strong p-4">
          Żadne źródło nie pasuje do tych filtrów. Zmień filtry albo wyczyść pole
          wyszukiwania.
        </p>
      )}
    </section>
  );
}

export function SourceCatalog() {
  const { state, reload } = useLoad("sources", getSources);

  if (state.status === "loading") return <LoadingBlock label="Wczytuję katalog źródeł…" />;
  if (state.status === "error") return <ErrorBlock error={state.error} onRetry={reload} />;

  const { corpus, rules, sources } = state.data;

  return (
    <div className="space-y-12">
      <CorpusSummary corpus={corpus} />

      {rules.length > 0 ? (
        <section aria-labelledby="zasady">
          <h2 id="zasady" className="text-2xl font-semibold">
            Zasady kwalifikowania źródeł
          </h2>
          <ul className="mt-3 max-w-[46rem] list-disc space-y-2 pl-6 text-lg">
            {rules.map((rule, index) => (
              <li key={index}>{rule}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <SourceList sources={sources} />
    </div>
  );
}

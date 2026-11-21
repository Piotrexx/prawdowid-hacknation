import { Disclosure } from "@/components/ui/Disclosure";
import { formatDateTime, formatInteger, formatSeconds, formatUsd } from "@/lib/format";
import { RETRIEVAL_LABELS, channelLabel } from "@/lib/labels";
import type { CheckResponse } from "@/lib/types";

export function TechnicalDetails({ result }: { result: CheckResponse }) {
  const { meta } = result;
  const model = [meta.provider, meta.model].filter(Boolean).join(" / ");
  const imageMetadata = Object.entries(result.input.image_metadata ?? {});

  const rows: Array<[string, string]> = [
    ["Czas sprawdzania", formatSeconds(meta.duration_ms)],
    ["Model językowy", model || "nie użyto"],
    ["Liczba wywołań modelu", formatInteger(meta.llm_calls)],
    [
      "Tokeny (wejście / wyjście)",
      `${formatInteger(meta.tokens_in)} / ${formatInteger(meta.tokens_out)}`,
    ],
  ];
  if (meta.cost_usd !== null) rows.push(["Szacowany koszt", formatUsd(meta.cost_usd)]);
  rows.push(
    ["Tryb wyszukiwania", RETRIEVAL_LABELS[meta.retrieval_mode] ?? meta.retrieval_mode],
    ["Wersja zbioru źródeł", meta.corpus_version || "brak danych"],
    ["Miejsce przetwarzania", meta.processing_location || "brak danych"],
    ["Odpowiedź z pamięci podręcznej", meta.cached ? "tak" : "nie"],
    ["Kanał", channelLabel(result.channel)],
    ["Data sprawdzenia", formatDateTime(result.created_at) ?? "brak danych"],
    ["Identyfikator", result.id],
  );
  for (const [key, value] of imageMetadata) rows.push([`Obraz: ${key}`, value]);

  return (
    <Disclosure summary="Szczegóły techniczne">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        {rows.map(([label, value]) => (
          <div key={label} className="sm:contents">
            <dt className="text-muted">{label}</dt>
            <dd className="font-medium break-words">{value}</dd>
          </div>
        ))}
      </dl>
    </Disclosure>
  );
}

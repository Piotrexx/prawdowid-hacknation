import { Disclosure } from "@/components/ui/Disclosure";
import { formatDateTime, formatInteger, formatSeconds, formatUsd } from "@/lib/format";
import { channelLabel } from "@/lib/labels";
import type { CheckResponse } from "@/lib/types";

export function TechnicalDetails({ result }: { result: CheckResponse }) {
  const { meta } = result;

  const rows: Array<[string, string]> = [
    ["Czas sprawdzania", formatSeconds(meta.duration_ms)],
    ["Model werdyktu (DeepSeek)", [meta.provider, meta.model].filter(Boolean).join(" / ") || "nie użyto"],
    ["Model słów kluczowych (Bielik)", meta.bielik_model || "nie użyto"],
    ["Liczba wywołań LLM", formatInteger(meta.llm_calls)],
    [
      "Tokeny DeepSeek (wejście / wyjście)",
      `${formatInteger(meta.tokens_in)} / ${formatInteger(meta.tokens_out)}`,
    ],
  ];
  if (meta.cost_usd !== null) rows.push(["Szacowany koszt", formatUsd(meta.cost_usd)]);
  rows.push(
    ["Miejsce przetwarzania", meta.processing_location || "brak danych"],
    ["Odpowiedź z pamięci podręcznej", meta.cached ? "tak" : "nie"],
    ["Kanał", channelLabel(result.channel)],
    ["Data sprawdzenia", formatDateTime(result.created_at) ?? "brak danych"],
    ["Identyfikator", result.id],
  );

  if (meta.stages_ms && Object.keys(meta.stages_ms).length > 0) {
    rows.push(["Szczegółowe czasy (ms)", ""]);
    for (const [stage, ms] of Object.entries(meta.stages_ms)) {
      rows.push([`  ${stage}`, formatInteger(ms)]);
    }
  }

  return (
    <Disclosure summary="Szczegóły techniczne">
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        {rows.map(([label, value], index) => (
          <div key={`${label}-${index}`} className="sm:contents">
            <dt className="text-muted">{label}</dt>
            <dd className="font-medium break-words">{value}</dd>
          </div>
        ))}
      </dl>
    </Disclosure>
  );
}
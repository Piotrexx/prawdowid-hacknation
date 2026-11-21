"use client";

import { CircleCheck, RotateCcw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { LoadingBlock } from "@/components/ui/LoadState";
import { Tag } from "@/components/ui/Tag";
import { getHealth } from "@/lib/api";
import { formatDateTime, formatInteger, plural } from "@/lib/format";
import { RETRIEVAL_LABELS } from "@/lib/labels";
import { useLoad } from "@/lib/useLoad";

export function HealthBlock() {
  const { state, reload } = useLoad("health", getHealth);

  if (state.status === "loading") {
    return <LoadingBlock label="Pobieram aktualne dane z serwera…" />;
  }

  if (state.status === "error") {
    return (
      <div className="space-y-3 rounded-xl border border-dashed border-line-strong p-4">
        <p>
          Nie udało się teraz pobrać danych z serwera. Pozostałe informacje na tej
          stronie nadal obowiązują.
        </p>
        <Button onClick={reload}>
          <RotateCcw aria-hidden="true" className="size-5" />
          Spróbuj ponownie
        </Button>
      </div>
    );
  }

  const health = state.data;
  const { corpus } = health;
  const model = health.llm_configured
    ? [health.llm_provider, health.llm_model].filter(Boolean).join(" / ")
    : "nie skonfigurowano";

  const rows: Array<[string, string]> = [
    ["Model językowy", model || "brak danych"],
    ["Miejsce przetwarzania danych", health.processing_location || "brak danych"],
    [
      "Czas przechowywania zapisów",
      `${health.retention_days} ${plural(health.retention_days, "dzień", "dni", "dni")}`,
    ],
    ["Sposób wyszukiwania", RETRIEVAL_LABELS[health.retrieval_mode] ?? health.retrieval_mode],
    ["Dokumenty w zbiorze źródeł", formatInteger(corpus.documents)],
    ["Fragmenty dokumentów", formatInteger(corpus.passages)],
    ["Domeny internetowe", formatInteger(corpus.domains)],
    ["Wersja zbioru źródeł", corpus.version || "brak danych"],
    ["Zbiór zbudowano", formatDateTime(corpus.built_at) ?? "brak danych"],
  ];

  return (
    <div className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <p>
        {health.status === "ok" ? (
          <Tag tone="ok" icon={CircleCheck}>
            System działa
          </Tag>
        ) : (
          <Tag tone="warn" icon={TriangleAlert}>
            System działa w ograniczonym zakresie
          </Tag>
        )}
      </p>
      <dl className="mt-3 space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="sm:grid sm:grid-cols-[16rem_1fr] sm:gap-3">
            <dt className="text-muted">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

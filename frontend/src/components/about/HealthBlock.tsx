"use client";

import { CircleCheck, RotateCcw, TriangleAlert, Cpu, Database } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { LoadingBlock } from "@/components/ui/LoadState";
import { Tag } from "@/components/ui/Tag";
import { getHealth } from "@/lib/api";
import { formatDateTime, formatInteger, plural } from "@/lib/format";
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
  const model = health.llm_configured
    ? [health.llm_provider, health.llm_model].filter(Boolean).join(" / ")
    : "nie skonfigurowano";
  const bielikModel = health.bielik_configured && health.bielik_model
    ? health.bielik_model
    : "nie skonfigurowano";

  const rows: Array<[string, string]> = [
    ["Model werdyktu (DeepSeek)", model],
    ["Model słów kluczowych (Bielik)", bielikModel],
    ["Google Fact Check API", health.google_factcheck_configured ? "skonfigurowane" : "nie skonfigurowane"],
    ["Miejsce przetwarzania danych", health.processing_location || "brak danych"],
    [
      "Czas przechowywania zapisów",
      `${health.retention_days} ${plural(health.retention_days, "dzień", "dni", "dni")}`,
    ],
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
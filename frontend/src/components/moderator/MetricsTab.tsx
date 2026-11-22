import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { StatTile } from "@/components/ui/StatTile";
import { getMetrics } from "@/lib/api";
import { formatInteger, formatPercent, formatSeconds, formatUsd } from "@/lib/format";
import { CHECK_STATUS_LABELS, VERDICT_LABELS, channelLabel, labelFor } from "@/lib/labels";
import { CountTable } from "./DataTable";
import { useAdminData, type AdminAccess } from "./useAdminData";

export function MetricsTab({ access }: { access: AdminAccess }) {
  const { state, reload } = useAdminData(access, "metrics", getMetrics);

  if (state.status === "loading") return <LoadingBlock label="Wczytuję statystyki…" />;
  if (state.status === "error") return <ErrorBlock error={state.error} onRetry={reload} />;

  const metrics = state.data;

  return (
    <div className="space-y-8">
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Wszystkie analizy" value={formatInteger(metrics.checks_total)} />
        <StatTile
          label="Odsetek wstrzymań od oceny"
          value={formatPercent(metrics.abstention_rate)}
          hint="Jak często system uznaje, że dowodów jest za mało."
        />
        <StatTile label="Mediana czasu" value={formatSeconds(metrics.median_duration_ms)} />
        <StatTile
          label="Czas p95"
          value={formatSeconds(metrics.p95_duration_ms)}
          hint="95% analiz trwa krócej."
        />
        <StatTile
          label="Tokeny (wejście / wyjście)"
          value={`${formatInteger(metrics.tokens_in)} / ${formatInteger(metrics.tokens_out)}`}
        />
        <StatTile label="Koszt łączny" value={formatUsd(metrics.cost_usd_total)} />
        <StatTile
          label="Koszt na 1000 analiz"
          value={formatUsd(metrics.cost_usd_per_1000)}
        />
        <StatTile label="Otwarte twierdzenia" value={formatInteger(metrics.open_cases)} />
      </dl>

      <div className="grid gap-6 lg:grid-cols-2">
        <CountTable
          caption="Analizy według stanu"
          keyHeader="Stan"
          counts={metrics.by_status}
          label={(key) => labelFor(CHECK_STATUS_LABELS, key)}
        />
        <CountTable
          caption="Analizy według kanału"
          keyHeader="Kanał"
          counts={metrics.by_channel}
          label={channelLabel}
        />
        <CountTable
          caption="Twierdzenia według oceny"
          keyHeader="Ocena"
          counts={metrics.by_verdict}
          label={(key) => labelFor(VERDICT_LABELS, key)}
        />
        <CountTable caption="Błędy według kodu" keyHeader="Kod błędu" counts={metrics.errors} />
        <CountTable
          caption="Zdarzenia bezpieczeństwa według rodzaju"
          keyHeader="Rodzaj"
          counts={metrics.security_events}
        />
      </div>
    </div>
  );
}

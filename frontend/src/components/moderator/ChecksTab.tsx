import Link from "next/link";
import { VerdictBadge } from "@/components/result/VerdictBadge";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { getRecentChecks } from "@/lib/api";
import { formatSeconds, formatShortDateTime, formatUsd } from "@/lib/format";
import { CHECK_STATUS_LABELS, channelLabel, inputKindLabel, labelFor } from "@/lib/labels";
import { checkPath } from "@/lib/links";
import { DataTable } from "./DataTable";
import { useAdminData, type AdminAccess } from "./useAdminData";

export function ChecksTab({ access }: { access: AdminAccess }) {
  const { state, reload } = useAdminData(access, "checks", getRecentChecks);

  if (state.status === "loading") return <LoadingBlock label="Wczytuję zgłoszenia…" />;
  if (state.status === "error") return <ErrorBlock error={state.error} onRetry={reload} />;

  const rows = state.data.map((check) => ({
    key: check.id,
    cells: [
      <span key="time" className="whitespace-nowrap">
        {formatShortDateTime(check.created_at) ?? "brak daty"}
      </span>,
      channelLabel(check.channel),
      labelFor(CHECK_STATUS_LABELS, check.status),
      inputKindLabel(check.input_kind),
      <Link key="preview" href={checkPath(check.id)} className="link block min-w-48">
        {check.input_preview || "(bez podglądu)"}
      </Link>,
      check.verdicts.length > 0 ? (
        <span key="verdicts" className="flex min-w-40 flex-wrap gap-1">
          {check.verdicts.map((verdict, index) => (
            <VerdictBadge key={index} verdict={verdict} />
          ))}
        </span>
      ) : (
        "brak"
      ),
      <span key="duration" className="whitespace-nowrap tabular-nums">
        {formatSeconds(check.duration_ms)}
      </span>,
      <span key="cost" className="whitespace-nowrap tabular-nums">
        {formatUsd(check.cost_usd)}
      </span>,
    ],
  }));

  return (
    <DataTable
      caption="Ostatnie zgłoszenia (do 50)"
      columns={["Czas", "Kanał", "Stan", "Rodzaj", "Treść", "Oceny", "Czas trwania", "Koszt"]}
      rows={rows}
      emptyText="Nie ma jeszcze żadnych zgłoszeń."
    />
  );
}

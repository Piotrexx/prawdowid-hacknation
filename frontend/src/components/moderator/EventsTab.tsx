import Link from "next/link";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { getSecurityEvents } from "@/lib/api";
import { formatShortDateTime } from "@/lib/format";
import { checkPath } from "@/lib/links";
import { DataTable } from "./DataTable";
import { useAdminData, type AdminAccess } from "./useAdminData";

export function EventsTab({ access }: { access: AdminAccess }) {
  const { state, reload } = useAdminData(access, "events", getSecurityEvents);

  if (state.status === "loading") return <LoadingBlock label="Wczytuję zdarzenia…" />;
  if (state.status === "error") return <ErrorBlock error={state.error} onRetry={reload} />;

  const rows = state.data.map((event) => ({
    key: event.id,
    cells: [
      <span key="time" className="whitespace-nowrap">
        {formatShortDateTime(event.created_at) ?? "brak daty"}
      </span>,
      event.kind,
      event.origin,
      event.detail,
      event.check_id ? (
        <Link key="check" href={checkPath(event.check_id)} className="link">
          Otwórz<span className="sr-only"> analizę {event.check_id}</span>
        </Link>
      ) : (
        "brak"
      ),
    ],
  }));

  return (
    <DataTable
      caption="Ostatnie zdarzenia bezpieczeństwa (do 50)"
      columns={["Czas", "Rodzaj", "Pochodzenie", "Szczegóły", "Analiza"]}
      rows={rows}
      emptyText="Nie odnotowano żadnych zdarzeń."
    />
  );
}

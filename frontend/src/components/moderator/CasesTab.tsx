import { useState } from "react";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { getCases } from "@/lib/api";
import { plural } from "@/lib/format";
import { CASE_STATUSES, CASE_STATUS_LABELS } from "@/lib/labels";
import type { CaseStatus } from "@/lib/types";
import { CaseCard } from "./CaseCard";
import { useAdminData, type AdminAccess } from "./useAdminData";

export function CasesTab({ access }: { access: AdminAccess }) {
  const [filter, setFilter] = useState<CaseStatus | "all">("open");
  const { state, reload, mutate } = useAdminData(access, `cases:${filter}`, (token, signal) =>
    getCases(token, filter === "all" ? null : filter, signal),
  );

  return (
    <div className="space-y-4">
      <label className="block max-w-xs font-medium">
        Pokaż sprawy
        <select
          value={filter}
          onChange={(event) => setFilter(event.target.value as CaseStatus | "all")}
          className="mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3"
        >
          <option value="all">Wszystkie</option>
          {CASE_STATUSES.map((value) => (
            <option key={value} value={value}>
              {CASE_STATUS_LABELS[value]}
            </option>
          ))}
        </select>
      </label>

      {state.status === "loading" ? <LoadingBlock label="Wczytuję sprawy…" /> : null}
      {state.status === "error" ? <ErrorBlock error={state.error} onRetry={reload} /> : null}
      {state.status === "ready" ? (
        <>
          <p role="status" className="text-muted">
            {state.data.length === 0
              ? "Brak spraw o tym stanie."
              : `${state.data.length} ${plural(state.data.length, "sprawa", "sprawy", "spraw")}.`}
          </p>
          <ul className="space-y-4">
            {state.data.map((item) => (
              <CaseCard
                key={item.id}
                item={item}
                access={access}
                onUpdated={(updated) =>
                  mutate((cases) =>
                    cases.map((current) => (current.id === updated.id ? updated : current)),
                  )
                }
              />
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

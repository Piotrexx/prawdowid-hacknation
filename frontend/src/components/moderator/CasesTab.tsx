import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { getCases } from "@/lib/api";
import { plural } from "@/lib/format";
import { CASE_STATUSES, CASE_STATUS_LABELS } from "@/lib/labels";
import { checkPath } from "@/lib/links";
import type { CaseOut, CaseStatus } from "@/lib/types";
import { CaseCard } from "./CaseCard";
import { useAdminData, type AdminAccess } from "./useAdminData";

const FILTER_DOT_HEX: Record<CaseStatus, string> = {
  open: "#22c55e",
  in_review: "#f97316",
  resolved: "#0052a5",
};

function groupByArticle(cases: CaseOut[]): Array<{ checkId: string | null; items: CaseOut[] }> {
  const grouped = new Map<string, CaseOut[]>();
  const orphans: CaseOut[] = [];

  for (const c of cases) {
    const key = c.check_ids[0] ?? null;
    if (!key) {
      orphans.push(c);
      continue;
    }
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(c);
  }

  const result: Array<{ checkId: string | null; items: CaseOut[] }> = [];
  for (const [checkId, items] of grouped) {
    result.push({ checkId, items });
  }
  if (orphans.length > 0) result.push({ checkId: null, items: orphans });
  return result;
}

export function CasesTab({ access }: { access: AdminAccess }) {
  const [filter, setFilter] = useState<CaseStatus | "all">("open");
  const { state, reload, mutate } = useAdminData(access, `cases:${filter}`, (token, signal) =>
    getCases(token, filter === "all" ? null : filter, signal),
  );

  const groups = state.status === "ready" ? groupByArticle(state.data) : [];
  const totalCases = state.status === "ready" ? state.data.length : 0;

  return (
    <div className="space-y-4">
      <label className="block max-w-xs font-medium">
        Pokaż twierdzenia
        <div className="relative mt-1">
          {filter !== "all" ? (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-2.5 -translate-y-1/2 rounded-full"
              style={{ backgroundColor: FILTER_DOT_HEX[filter as CaseStatus] }}
            />
          ) : null}
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value as CaseStatus | "all")}
            className={`block min-h-11 w-full rounded-lg border border-line-strong bg-surface py-0 pr-3 ${filter !== "all" ? "pl-8" : "pl-3"}`}
          >
            <option value="all">Wszystkie</option>
            {CASE_STATUSES.map((value) => (
              <option key={value} value={value}>
                {CASE_STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </div>
      </label>

      {state.status === "loading" ? <LoadingBlock label="Wczytuję twierdzenia…" /> : null}
      {state.status === "error" ? <ErrorBlock error={state.error} onRetry={reload} /> : null}
      {state.status === "ready" ? (
        <>
          <p role="status" className="text-muted">
            {totalCases === 0
              ? "Brak twierdzeń o tym stanie."
              : `${totalCases} ${plural(totalCases, "twierdzenie", "twierdzenia", "twierdzeń")} w ${groups.length} ${plural(groups.length, "artykule", "artykułach", "artykułach")}.`}
          </p>
          <div className="space-y-6">
            {groups.map(({ checkId, items }, index) => (
              <div key={checkId ?? "orphans"} className="rounded-xl border border-line-mid bg-subtle">
                <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                    <span className="font-semibold text-ink">Artykuł nr {index + 1}</span>
                    <span aria-hidden="true" className="text-muted">
                    
                    </span>
                    {checkId ? (
                      <Link
                        href={checkPath(checkId)}
                        className="inline-flex min-h-11 items-center gap-1 text-link hover:underline"
                      >
                        <ExternalLink className="size-4" aria-hidden="true" />
                        Wyniki analizy
                      </Link>
                    ) : (
                      <span className="text-sm text-muted italic">brak powiązanej analizy</span>
                    )}
                  </div>
                  <span className="inline-flex shrink-0 items-center border border-line-strong bg-surface px-2.5 py-1 text-xs font-bold tracking-[0.02em] uppercase tabular-nums text-ink">
                    {items.length} {plural(items.length, "twierdzenie", "twierdzenia", "twierdzeń")}
                  </span>
                </div>
                <ul className="divide-y divide-line p-4 space-y-4">
                  {items.map((item) => (
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
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

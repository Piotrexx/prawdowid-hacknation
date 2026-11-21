"use client";

import { SearchX } from "lucide-react";
import Link from "next/link";
import { CheckResult } from "@/components/result/CheckResult";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { ApiError, getCheck } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useLoad } from "@/lib/useLoad";

const HOME_LINK_CLASS =
  "inline-flex min-h-11 items-center rounded-lg bg-accent px-4 font-medium text-on-accent hover:bg-accent-hover";

export function PermalinkView({ id }: { id: string }) {
  const { state, reload } = useLoad(`check:${id}`, (signal) => getCheck(id, signal));

  if (state.status === "loading") {
    return <LoadingBlock label="Wczytuję wynik sprawdzenia…" />;
  }

  if (state.status === "error") {
    const notFound = state.error instanceof ApiError && state.error.kind === "not_found";
    if (!notFound) return <ErrorBlock error={state.error} onRetry={reload} />;
    return (
      <div className="flex gap-4 rounded-xl border-2 border-dashed border-line-strong bg-surface p-5">
        <SearchX aria-hidden="true" className="mt-1 size-7 shrink-0 text-muted" />
        <div className="space-y-3">
          <h2 className="text-xl font-semibold">
            Nie znaleziono sprawdzenia. Mogło zostać usunięte.
          </h2>
          <p className="text-muted">
            Sprawdź, czy link jest pełny. Zapisy są też usuwane po pewnym czasie albo
            na prośbę osoby, która je utworzyła.
          </p>
          <Link href="/" className={HOME_LINK_CLASS}>
            Sprawdź nową treść
          </Link>
        </div>
      </div>
    );
  }

  const checkedAt = formatDateTime(state.data.created_at);

  return (
    <div className="space-y-6">
      {checkedAt ? (
        <p className="text-muted">
          Sprawdzono: {checkedAt}. Od tego czasu informacje mogły się zmienić.
        </p>
      ) : null}
      <CheckResult result={state.data} />
      <Link href="/" className={HOME_LINK_CLASS}>
        Sprawdź coś innego
      </Link>
    </div>
  );
}

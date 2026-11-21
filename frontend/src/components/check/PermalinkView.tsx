"use client";

import { SearchX } from "lucide-react";
import Link from "next/link";
import { ResultView } from "@/components/result/ResultView";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { ApiError, getCheck } from "@/lib/api";
import { cachedResult } from "@/lib/resultCache";
import { useLoad } from "@/lib/useLoad";

const HOME_LINK_CLASS =
  "inline-flex min-h-11 items-center bg-accent px-5 font-semibold text-on-accent hover:bg-accent-hover";

export function PermalinkView({ id }: { id: string }) {
  // A check that just finished on the home page is shown without fetching it again.
  const cached = cachedResult(id);
  if (cached) return <ResultView result={cached} focusHeading />;
  return <LoadedResult id={id} />;
}

function LoadedResult({ id }: { id: string }) {
  const { state, reload } = useLoad(`check:${id}`, (signal) => getCheck(id, signal));

  if (state.status === "ready") return <ResultView result={state.data} />;

  return (
    <div className="mx-auto w-full max-w-[52rem] px-5 py-8 sm:p-10">
      <h1 className="text-[1.875rem] leading-tight font-bold">Wynik sprawdzenia</h1>
      <div className="title-rule my-4" />
      {state.status === "loading" ? (
        <LoadingBlock label="Wczytuję wynik sprawdzenia…" />
      ) : state.error instanceof ApiError && state.error.kind === "not_found" ? (
        <div className="flex gap-4 border-2 border-dashed border-line-strong bg-surface p-5">
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
      ) : (
        <ErrorBlock error={state.error} onRetry={reload} />
      )}
    </div>
  );
}

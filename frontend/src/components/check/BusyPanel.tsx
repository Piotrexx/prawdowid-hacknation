import type { Ref } from "react";
import { Spinner } from "@/components/ui/Spinner";

/** Static description of the work in progress. It is not a progress bar: no step is ever marked done. */
export function BusyPanel({ panelRef }: { panelRef: Ref<HTMLDivElement> }) {
  return (
    <div
      ref={panelRef}
      tabIndex={-1}
      className="rounded-xl border border-line bg-surface p-5"
    >
      <p className="flex items-center gap-3 text-xl font-semibold">
        <Spinner className="size-7" />
        Sprawdzam w źródłach. To zwykle trwa do 30 sekund.
      </p>
      <p className="mt-4 text-muted">W tym czasie:</p>
      <ol className="mt-1 list-decimal space-y-1 pl-6">
        <li>wydzielam twierdzenia,</li>
        <li>szukam w źródłach,</li>
        <li>porównuję dowody.</li>
      </ol>
    </div>
  );
}

"use client";

import { Clock, ExternalLink, GitBranch, Network, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { EventGraphView } from "@/components/events/EventGraphView";
import { EventTimeline } from "@/components/events/EventTimeline";
import { Button } from "@/components/ui/Button";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { Tag } from "@/components/ui/Tag";
import { getEventGraph, rebuildEventGraph } from "@/lib/api";
import { cx } from "@/lib/cx";
import { describeError } from "@/lib/errors";
import { formatInteger } from "@/lib/format";
import type { EventGraphResponse } from "@/lib/types";
import { EventDetailPanel } from "./EventDetailPanel";
import { guarded, useAdminData, type AdminAccess } from "./useAdminData";

type View = "timeline" | "graph";
const WINDOWS = [30, 90, 365];

function WindowPicker({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <fieldset className="flex items-center gap-2">
      <legend className="sr-only">Zakres czasu mapy</legend>
      {WINDOWS.map((days) => (
        <label
          key={days}
          className={cx(
            "inline-flex min-h-11 cursor-pointer items-center border px-3 text-sm font-medium",
            value === days
              ? "border-accent bg-info-bg text-ink"
              : "border-line-strong bg-surface text-muted hover:bg-subtle",
          )}
        >
          <input
            type="radio"
            name="okno-mapy"
            className="sr-only"
            checked={value === days}
            onChange={() => onChange(days)}
          />
          {days} dni
        </label>
      ))}
    </fieldset>
  );
}

function ViewToggle({ value, onChange }: { value: View; onChange: (value: View) => void }) {
  return (
    <div className="inline-flex border border-line-strong bg-surface" role="group" aria-label="Widok mapy">
      {(
        [
          ["timeline", "Oś czasu", Clock],
          ["graph", "Graf", GitBranch],
        ] as const
      ).map(([key, label, Icon]) => (
        <button
          key={key}
          type="button"
          aria-pressed={value === key}
          onClick={() => onChange(key)}
          className={cx(
            "inline-flex min-h-11 items-center gap-2 px-4 text-sm font-semibold",
            value === key ? "bg-accent text-on-accent" : "text-muted hover:bg-subtle hover:text-ink",
          )}
        >
          <Icon aria-hidden="true" className="size-4" />
          {label}
        </button>
      ))}
    </div>
  );
}

function Stats({ graph }: { graph: EventGraphResponse }) {
  const events = graph.nodes.filter((node) => node.kind === "event");
  const proposed = events.reduce((sum, node) => sum + node.proposed_count, 0);
  const anchors = graph.nodes.filter((node) => node.kind === "anchor").length;
  return (
    <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
      <div className="flex items-center gap-2">
        <dt className="text-muted">Wydarzenia:</dt>
        <dd className="font-bold tabular-nums">{formatInteger(events.length)}</dd>
      </div>
      <div className="flex items-center gap-2">
        <dt className="text-muted">Propozycje:</dt>
        <dd className="font-bold tabular-nums">{formatInteger(proposed)}</dd>
      </div>
      <div className="flex items-center gap-2">
        <dt className="text-muted">Kotwice:</dt>
        <dd className="font-bold tabular-nums">{formatInteger(anchors)}</dd>
      </div>
    </dl>
  );
}

export function EventMapTab({ access }: { access: AdminAccess }) {
  const [view, setView] = useState<View>("timeline");
  const [windowDays, setWindowDays] = useState(90);
  const [includeProposed, setIncludeProposed] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);
  const { state, reload } = useAdminData(
    access,
    `graph:${windowDays}:${includeProposed}`,
    (token, signal) =>
      getEventGraph(
        token,
        { windowDays, includeProposed },
        signal,
      ),
  );

  async function rebuild() {
    if (
      !window.confirm(
        "Przebudować mapę od zera? Obecne wydarzenia i decyzje moderatora zostaną usunięte, a relacje policzone ponownie z zapisanych zgłoszeń.",
      )
    ) {
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      const result = await guarded(access, rebuildEventGraph(access.token, { reset: true }));
      setSelectedId(null);
      reload();
      setFeedback({
        ok: true,
        text: `Przebudowano mapę: ${result.processed_checks} zgłoszeń, ${result.events} wydarzeń, pominięto ${result.skipped}.`,
      });
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się przebudować mapy. ${describeError(error)}` });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-xl border border-line-mid bg-subtle p-4">
        <div className="space-y-3">
          <WindowPicker value={windowDays} onChange={setWindowDays} />
          <label className="flex min-h-11 items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={includeProposed}
              onChange={(event) => setIncludeProposed(event.target.checked)}
              className="size-4"
            />
            Pokazuj propozycje wymagające decyzji
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ViewToggle value={view} onChange={setView} />
          <Link
            href="/mapa"
            target="_blank"
            className="inline-flex min-h-11 items-center gap-1 text-sm text-link hover:underline"
          >
            <ExternalLink aria-hidden="true" className="size-4" />
            Podgląd publiczny
          </Link>
          <Button variant="secondary" onClick={reload} disabled={busy}>
            <RefreshCw aria-hidden="true" className="size-4" />
            Odśwież
          </Button>
          {access.isSuperuser ? (
            <Button variant="danger" onClick={() => void rebuild()} disabled={busy}>
              <Network aria-hidden="true" className="size-4" />
              Przebuduj mapę
            </Button>
          ) : null}
        </div>
      </div>

      <div role="status" aria-live="polite">
        {feedback ? (
          <p
            className={cx(
              "rounded-lg border px-4 py-3 font-medium",
              feedback.ok
                ? "border-ok-line bg-ok-bg text-ok-fg"
                : "border-bad-line bg-bad-bg text-bad-fg",
            )}
          >
            {feedback.text}
          </p>
        ) : null}
      </div>

      {state.status === "loading" ? <LoadingBlock label="Wczytuję mapę wydarzeń…" /> : null}
      {state.status === "error" ? <ErrorBlock error={state.error} onRetry={reload} /> : null}
      {state.status === "ready" ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Stats graph={state.data} />
            <Tag tone="neutral">
              Okno {state.data.window_days} dni
            </Tag>
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(22rem,1fr)]">
            <div className="min-w-0">
              {view === "timeline" ? (
                <EventTimeline
                  graph={state.data}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              ) : (
                <EventGraphView
                  graph={state.data}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              )}
            </div>
            <div className="min-w-0">
              {selectedId ? (
                <EventDetailPanel
                  key={selectedId}
                  access={access}
                  eventId={selectedId}
                  events={state.data.nodes}
                  onSelect={setSelectedId}
                  onChanged={reload}
                />
              ) : (
                <div className="rounded-xl border border-line-mid bg-subtle p-5">
                  <h2 className="font-semibold">Wybierz wydarzenie</h2>
                  <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                    Kliknij wydarzenie na osi czasu albo węzeł na grafie. Zobaczysz
                    zgłoszenia, propozycje do decyzji, relacje i znane incydenty.
                  </p>
                  <p className="mt-3 text-xs text-muted">
                    Graf jest kontekstem analitycznym. Przynależność do wydarzenia nigdy nie
                    przesądza o prawdziwości twierdzenia — werdykt wynika wyłącznie z cytatów
                    w źródłach.
                  </p>
                </div>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

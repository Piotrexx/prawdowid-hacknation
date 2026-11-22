"use client";

import { Clock, ExternalLink, GitBranch, Info } from "lucide-react";
import { useState } from "react";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { Tag } from "@/components/ui/Tag";
import { getPublicEventMap } from "@/lib/api";
import { cx } from "@/lib/cx";
import { formatDate, formatInteger } from "@/lib/format";
import { EVENT_RELATION_LABELS, VERDICT_LABELS } from "@/lib/labels";
import { useLoad } from "@/lib/useLoad";
import type { EventGraphResponse, GraphNode, Verdict } from "@/lib/types";
import { EventGraphView } from "./EventGraphView";
import { EventTimeline } from "./EventTimeline";

type View = "timeline" | "graph";
const WINDOWS = [30, 90, 365];

function PublicStats({ graph }: { graph: EventGraphResponse }) {
  const events = graph.nodes.filter((node) => node.kind === "event");
  const reports = events.reduce((sum, node) => sum + node.member_count, 0);
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
      <span>
        Wydarzenia: <strong className="tabular-nums text-ink">{formatInteger(events.length)}</strong>
      </span>
      <span>
        Zgłoszenia w agregacie:{" "}
        <strong className="tabular-nums text-ink">{formatInteger(reports)}</strong>
      </span>
      <span>
        Zakres: <strong className="text-ink">{graph.window_days} dni</strong>
      </span>
    </div>
  );
}

function PublicDetail({
  graph,
  node,
}: {
  graph: EventGraphResponse;
  node: GraphNode;
}) {
  const anchorNodes = graph.nodes.filter(
    (candidate) =>
      candidate.kind === "anchor" &&
      graph.edges.some(
        (edge) =>
          edge.relation === "anchor" &&
          edge.source === node.id &&
          edge.target === candidate.id,
      ),
  );
  const neighbours = graph.edges
    .filter(
      (edge) =>
        edge.relation !== "anchor" &&
        (edge.source === node.id || edge.target === node.id),
    )
    .map((edge) => {
      const otherId = edge.source === node.id ? edge.target : edge.source;
      return {
        edge,
        event: graph.nodes.find((candidate) => candidate.id === otherId),
      };
    })
    .filter((item) => item.event);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-line-strong bg-subtle p-4">
        <p className="eyebrow">Wydarzenie</p>
        <h2 className="mt-1 text-xl font-bold text-balance">{node.label}</h2>
        <p className="mt-1 text-sm text-muted">
          {formatInteger(node.member_count)} zgłoszeń w agregacie
          {node.last_seen ? ` · ostatnie: ${formatDate(node.last_seen)}` : ""}
        </p>
        {node.risk === "high" ? (
          <div className="mt-2">
            <Tag tone="warn">Temat wysokiego ryzyka</Tag>
          </div>
        ) : null}
        {node.keywords.length > 0 ? (
          <p className="mt-2 text-sm text-muted">{node.keywords.join(" · ")}</p>
        ) : null}
        {Object.keys(node.verdicts).length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {Object.entries(node.verdicts).map(([verdict, count]) => (
              <li key={verdict}>
                <span className="inline-flex border border-line bg-surface px-2 py-0.5 text-xs">
                  {VERDICT_LABELS[verdict as Verdict] ?? verdict}
                  <span className="ml-1 font-bold tabular-nums">{count}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="rounded-xl border border-line bg-surface p-4">
        <h3 className="font-semibold">Znane incydenty i weryfikacje</h3>
        {anchorNodes.length === 0 ? (
          <p className="mt-2 text-sm text-muted">
            Brak publicznych materiałów powiązanych z tym wydarzeniem.
          </p>
        ) : (
          <ul className="mt-3 space-y-3">
            {anchorNodes.map((anchor) => (
              <li key={anchor.id} className="border-b border-line pb-3 last:border-b-0 last:pb-0">
                {anchor.url ? (
                  <a
                    href={anchor.url}
                    target="_blank"
                    rel="noreferrer"
                    className="link inline-flex items-center gap-1 font-medium"
                  >
                    {anchor.label}
                    <ExternalLink aria-hidden="true" className="size-3.5" />
                  </a>
                ) : (
                  <span className="font-medium">{anchor.label}</span>
                )}
                {anchor.subtitle ? (
                  <p className="text-xs text-muted">{anchor.subtitle}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      {neighbours.length > 0 ? (
        <div className="rounded-xl border border-line bg-surface p-4">
          <h3 className="font-semibold">Powiązane wydarzenia</h3>
          <ul className="mt-3 space-y-2">
            {neighbours.map(({ edge, event }) => (
              <li key={edge.id} className="text-sm">
                <span className="text-muted">
                  {EVENT_RELATION_LABELS[edge.relation]}:
                </span>{" "}
                <span className="font-medium">{event?.label}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function PublicEventMap() {
  const [view, setView] = useState<View>("timeline");
  const [windowDays, setWindowDays] = useState(90);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { state, reload } = useLoad(`public-map:${windowDays}`, (signal) =>
    getPublicEventMap({ windowDays }, signal),
  );

  const selected =
    state.status === "ready"
      ? state.data.nodes.find((node) => node.id === selectedId && node.kind === "event")
      : undefined;

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-info-line bg-info-bg p-4 text-sm">
        <p className="flex items-start gap-2">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>
            To mapa zagregowana. Pokazujemy wyłącznie wydarzenia, które zgłosiło co najmniej{" "}
            <strong>{state.status === "ready" ? state.data.min_members : 3}</strong> osób.
            Nie publikujemy treści zgłoszeń, numerów sesji ani danych osobowych.
          </span>
        </p>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <fieldset className="flex items-center gap-2">
          <legend className="sr-only">Zakres czasu</legend>
          {WINDOWS.map((days) => (
            <label
              key={days}
              className={cx(
                "inline-flex min-h-11 cursor-pointer items-center border px-3 text-sm font-medium",
                windowDays === days
                  ? "border-accent bg-info-bg text-ink"
                  : "border-line-strong bg-surface text-muted hover:bg-subtle",
              )}
            >
              <input
                type="radio"
                name="okno-mapy-publicznej"
                className="sr-only"
                checked={windowDays === days}
                onChange={() => {
                  setWindowDays(days);
                  setSelectedId(null);
                }}
              />
              {days} dni
            </label>
          ))}
        </fieldset>

        <div
          className="inline-flex border border-line-strong bg-surface"
          role="group"
          aria-label="Widok mapy"
        >
          {(
            [
              ["timeline", "Oś czasu", Clock],
              ["graph", "Graf", GitBranch],
            ] as const
          ).map(([key, label, Icon]) => (
            <button
              key={key}
              type="button"
              aria-pressed={view === key}
              onClick={() => setView(key)}
              className={cx(
                "inline-flex min-h-11 items-center gap-2 px-4 text-sm font-semibold",
                view === key
                  ? "bg-accent text-on-accent"
                  : "text-muted hover:bg-subtle hover:text-ink",
              )}
            >
              <Icon aria-hidden="true" className="size-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {state.status === "loading" ? <LoadingBlock label="Wczytuję mapę wydarzeń…" /> : null}
      {state.status === "error" ? <ErrorBlock error={state.error} onRetry={reload} /> : null}
      {state.status === "ready" ? (
        <>
          <PublicStats graph={state.data} />
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,1fr)]">
            <div className="min-w-0">
              {view === "timeline" ? (
                <EventTimeline
                  graph={state.data}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  publicView
                />
              ) : (
                <EventGraphView
                  graph={state.data}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  ariaLabel="Publiczna mapa powiązań wydarzeń"
                />
              )}
            </div>
            <div className="min-w-0">
              {selected ? (
                <PublicDetail graph={state.data} node={selected} />
              ) : (
                <div className="rounded-xl border border-line-mid bg-subtle p-5">
                  <h2 className="font-semibold">Wybierz wydarzenie</h2>
                  <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                    Kliknij wydarzenie, aby zobaczyć zagregowane werdykty, znane incydenty
                    i powiązane tematy. Mapa nie wskazuje sprawców ani nie przypisuje winy.
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

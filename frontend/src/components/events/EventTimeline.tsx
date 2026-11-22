"use client";

import { ExternalLink, ShieldAlert } from "lucide-react";
import { Tag } from "@/components/ui/Tag";
import { cx } from "@/lib/cx";
import { formatDate, formatInteger } from "@/lib/format";
import { VERDICT_LABELS } from "@/lib/labels";
import type { EventGraphResponse, GraphNode, Verdict } from "@/lib/types";

interface EventTimelineProps {
  graph: EventGraphResponse;
  selectedId?: string | null;
  onSelect: (id: string) => void;
  publicView?: boolean;
}

const MONTH_FORMAT = new Intl.DateTimeFormat("pl-PL", {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

function monthKey(value: string | null): string {
  return (value ?? "").slice(0, 7) || "bez-daty";
}

function monthLabel(value: string | null): string {
  if (!value) return "Bez daty";
  const date = new Date(`${value.slice(0, 7)}-01T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? "Bez daty" : MONTH_FORMAT.format(date);
}

function eventTime(node: GraphNode): number {
  const value = node.last_seen ?? node.first_seen;
  return value ? Date.parse(value) : 0;
}

function VerdictSummary({ verdicts }: { verdicts: Record<string, number> }) {
  const entries = Object.entries(verdicts).filter(([, count]) => count > 0);
  if (entries.length === 0) return null;
  return (
    <ul className="mt-3 flex flex-wrap gap-1.5">
      {entries.map(([verdict, count]) => (
        <li key={verdict}>
          <span className="inline-flex items-center border border-line bg-subtle px-2 py-0.5 text-xs">
            {VERDICT_LABELS[verdict as Verdict] ?? verdict}
            <span className="ml-1 font-bold tabular-nums">{count}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function EventTimeline({
  graph,
  selectedId,
  onSelect,
  publicView = false,
}: EventTimelineProps) {
  const events = graph.nodes
    .filter((node) => node.kind === "event")
    .sort((a, b) => eventTime(b) - eventTime(a));

  if (events.length === 0) {
    return (
      <p className="rounded-xl border border-line-mid bg-subtle px-4 py-6 text-muted">
        {publicView
          ? "Jeszcze za mało zgłoszeń, aby pokazać zagregowaną mapę wydarzeń."
          : "Brak wydarzeń w tym zakresie czasu."}
      </p>
    );
  }

  const groups = new Map<string, GraphNode[]>();
  for (const event of events) {
    const key = monthKey(event.last_seen ?? event.first_seen);
    const bucket = groups.get(key) ?? [];
    bucket.push(event);
    groups.set(key, bucket);
  }

  return (
    <div className="space-y-8">
      {[...groups.entries()].map(([key, nodes]) => (
        <section key={key} aria-labelledby={`miesiac-${key}`}>
          <h3
            id={`miesiac-${key}`}
            className="mb-3 text-sm font-bold tracking-[0.06em] text-muted uppercase"
          >
            {monthLabel(nodes[0].last_seen ?? nodes[0].first_seen)}
          </h3>
          <ol className="space-y-3">
            {nodes.map((node) => {
              const selected = node.id === selectedId;
              const anchors = graph.edges.filter(
                (edge) => edge.relation === "anchor" && edge.source === node.id,
              ).length;
              return (
                <li key={node.id}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => onSelect(node.id)}
                    className={cx(
                      "w-full rounded-xl border px-4 py-4 text-left transition-colors sm:px-5",
                      selected
                        ? "border-accent bg-info-bg"
                        : "border-line bg-surface hover:border-line-strong hover:bg-subtle",
                    )}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <span className="text-xs font-semibold tracking-wide text-muted uppercase">
                          Wydarzenie · {formatDate(node.first_seen ?? undefined) ?? "bez daty"}
                        </span>
                        <h4 className="mt-1 text-lg font-semibold text-balance">
                          {node.label}
                        </h4>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-1.5">
                        {node.risk === "high" ? (
                          <Tag tone="warn" icon={ShieldAlert}>
                            Wysokie ryzyko
                          </Tag>
                        ) : null}
                        <Tag tone="info">
                          {formatInteger(node.member_count)}{" "}
                          {node.member_count === 1 ? "zgłoszenie" : "zgłoszeń"}
                        </Tag>
                        {!publicView && node.proposed_count > 0 ? (
                          <Tag tone="warn">
                            {formatInteger(node.proposed_count)} do decyzji
                          </Tag>
                        ) : null}
                      </div>
                    </div>

                    {node.keywords.length > 0 ? (
                      <p className="mt-2 text-sm text-muted">
                        {node.keywords.slice(0, 5).join(" · ")}
                      </p>
                    ) : null}

                    <VerdictSummary verdicts={node.verdicts} />

                    <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted">
                      {anchors > 0 ? (
                        <span className="inline-flex items-center gap-1">
                          <ExternalLink aria-hidden="true" className="size-3.5" />
                          {formatInteger(anchors)}{" "}
                          {anchors === 1 ? "znany incydent" : "znanych incydentów"}
                        </span>
                      ) : null}
                      {node.last_seen ? (
                        <span>
                          Ostatnie zgłoszenie:{" "}
                          {formatDate(node.last_seen) ?? "brak daty"}
                        </span>
                      ) : null}
                    </div>
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}

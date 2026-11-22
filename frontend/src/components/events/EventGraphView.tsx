"use client";

import { useId, useMemo } from "react";
import { cx } from "@/lib/cx";
import { EVENT_RELATION_LABELS } from "@/lib/labels";
import type { EventGraphResponse, GraphNode } from "@/lib/types";

interface Point {
  x: number;
  y: number;
}

interface PositionedNode extends GraphNode {
  point: Point;
  radius: number;
}

interface EventGraphViewProps {
  graph: EventGraphResponse;
  selectedId?: string | null;
  onSelect: (id: string) => void;
  ariaLabel?: string;
  /** Domyślnie wybieralne są tylko wydarzenia; kotwice służą jako kontekst. */
  selectableKinds?: Array<"event" | "anchor">;
}

const WIDTH = 860;
const HEIGHT = 560;
const EVENT_COLOR = "#0052a5";
const EVENT_HIGH_COLOR = "#b42318";
const ANCHOR_COLOR = "#6b7280";
const PROPOSED_COLOR = "#c2410c";

function shortLabel(label: string, max = 30): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

function eventRadius(memberCount: number): number {
  return 11 + Math.min(15, Math.log2(Math.max(1, memberCount) + 1) * 4);
}

function layout(graph: EventGraphResponse): Map<string, PositionedNode> {
  const positions = new Map<string, PositionedNode>();
  const events = graph.nodes.filter((node) => node.kind === "event");
  const anchors = graph.nodes.filter((node) => node.kind === "anchor");
  const center = { x: WIDTH / 2, y: HEIGHT / 2 };

  const sorted = [...events].sort((a, b) =>
    (a.first_seen ?? a.id).localeCompare(b.first_seen ?? b.id),
  );

  sorted.forEach((node, index) => {
    const angle = (index / Math.max(1, sorted.length)) * Math.PI * 2 - Math.PI / 2;
    const ring = sorted.length <= 2 ? 70 : Math.min(220, 95 + sorted.length * 11);
    positions.set(node.id, {
      ...node,
      point: {
        x: center.x + Math.cos(angle) * ring,
        y: center.y + Math.sin(angle) * ring * 0.82,
      },
      radius: eventRadius(node.member_count),
    });
  });

  anchors.forEach((node, index) => {
    const parent = node.event_id ? positions.get(node.event_id) : undefined;
    const angle = (index / Math.max(1, anchors.length)) * Math.PI * 2;
    const base = parent?.point ?? center;
    const distance = parent ? 96 : 300;
    positions.set(node.id, {
      ...node,
      point: {
        x: Math.min(WIDTH - 30, Math.max(30, base.x + Math.cos(angle) * distance)),
        y: Math.min(HEIGHT - 30, Math.max(30, base.y + Math.sin(angle) * distance)),
      },
      radius: 7,
    });
  });

  return positions;
}

export function EventGraphView({
  graph,
  selectedId,
  onSelect,
  ariaLabel = "Graf powiązań wydarzeń",
  selectableKinds = ["event"],
}: EventGraphViewProps) {
  const titleId = useId();
  const positions = useMemo(() => layout(graph), [graph]);

  if (graph.nodes.length === 0) {
    return (
      <p className="rounded-xl border border-line-mid bg-subtle px-4 py-6 text-muted">
        Brak wydarzeń do pokazania w tym zakresie czasu.
      </p>
    );
  }

  return (
    <figure className="rounded-xl border border-line-mid bg-surface">
      <figcaption id={titleId} className="sr-only">
        {ariaLabel}. Wybierz wydarzenie, aby zobaczyć szczegóły.
      </figcaption>
      <div className="overflow-x-auto">
        <svg
          role="group"
          aria-labelledby={titleId}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="h-auto min-w-[640px] w-full"
        >
          <title>{ariaLabel}</title>
          <g>
            {graph.edges.map((edge) => {
              const source = positions.get(edge.source);
              const target = positions.get(edge.target);
              if (!source || !target) return null;
              const midX = (source.point.x + target.point.x) / 2;
              const midY = (source.point.y + target.point.y) / 2;
              const dx = target.point.x - source.point.x;
              const dy = target.point.y - source.point.y;
              const curve = 0.12;
              const control = { x: midX - dy * curve, y: midY + dx * curve };
              const proposed = edge.status === "proposed";
              return (
                <path
                  key={edge.id}
                  d={`M ${source.point.x} ${source.point.y} Q ${control.x} ${control.y} ${target.point.x} ${target.point.y}`}
                  fill="none"
                  stroke={proposed ? PROPOSED_COLOR : "#93a4b8"}
                  strokeWidth={proposed ? 1.8 : 1.3}
                  strokeDasharray={proposed ? "5 5" : undefined}
                  opacity={proposed ? 0.85 : 0.7}
                >
                  <title>
                    {EVENT_RELATION_LABELS[edge.relation]}
                    {edge.score !== null ? ` (${edge.score.toFixed(2)})` : ""}
                    {proposed ? " – propozycja" : ""}
                  </title>
                </path>
              );
            })}
          </g>
          <g>
            {[...positions.values()].map((node) => {
              const selected = node.id === selectedId;
              const isAnchor = node.kind === "anchor";
              const selectable = node.kind === "event" || selectableKinds.includes(node.kind);
              const color = isAnchor
                ? ANCHOR_COLOR
                : node.risk === "high"
                  ? EVENT_HIGH_COLOR
                  : EVENT_COLOR;
              return (
                <g
                  key={node.id}
                  role={selectable ? "button" : undefined}
                  tabIndex={selectable ? 0 : undefined}
                  aria-pressed={selectable ? selected : undefined}
                  aria-label={`${node.label}. ${
                    isAnchor
                      ? "Znany incydent"
                      : `${node.member_count} zgłoszeń${
                          node.proposed_count ? `, ${node.proposed_count} propozycji` : ""
                        }`
                  }`}
                  onClick={selectable ? () => onSelect(node.id) : undefined}
                  onKeyDown={
                    selectable
                      ? (event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            onSelect(node.id);
                          }
                        }
                      : undefined
                  }
                  className={selectable ? "cursor-pointer focus:outline-none" : undefined}
                >
                  <circle
                    cx={node.point.x}
                    cy={node.point.y}
                    r={node.radius + (selected ? 5 : 0)}
                    fill={selected ? "#dbeafe" : "#ffffff"}
                    stroke={selected ? "#1d4ed8" : color}
                    strokeWidth={selected ? 3 : 2}
                  />
                  {isAnchor ? (
                    <circle
                      cx={node.point.x}
                      cy={node.point.y}
                      r={2.4}
                      fill={ANCHOR_COLOR}
                    />
                  ) : (
                    <text
                      x={node.point.x}
                      y={node.point.y + 4}
                      textAnchor="middle"
                      fontSize={10}
                      fontWeight={700}
                      fill={color}
                    >
                      {node.member_count}
                    </text>
                  )}
                  <text
                    x={node.point.x}
                    y={node.point.y + node.radius + 14}
                    textAnchor="middle"
                    fontSize={isAnchor ? 9.5 : 10.5}
                    fontWeight={selected ? 700 : 500}
                    fill="#1f2937"
                  >
                    {shortLabel(node.label, isAnchor ? 24 : 30)}
                  </text>
                  <title>
                    {node.label}
                    {node.subtitle ? ` — ${node.subtitle}` : ""}
                  </title>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-2 border-t border-line px-4 py-3 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded-full border-2 border-[#0052a5]" /> wydarzenie
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded-full border-2 border-[#b42318]" /> wysokie ryzyko
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-[#6b7280]" /> znany incydent
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0 w-5 border-t-2 border-dashed border-[#c2410c]" /> propozycja
        </span>
      </div>
    </figure>
  );
}

export function eventNodeClass(selected: boolean): string {
  return cx(
    "w-full rounded-xl border px-4 py-4 text-left transition-colors",
    selected
      ? "border-accent bg-info-bg"
      : "border-line bg-surface hover:border-line-strong hover:bg-subtle",
  );
}

"use client";

import { ExternalLink, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorBlock, LoadingBlock } from "@/components/ui/LoadState";
import { Tag } from "@/components/ui/Tag";
import {
  getEventDetail,
  mergeEvents,
  reviewEventLink,
  reviewEventMember,
  splitEventMember,
} from "@/lib/api";
import { describeError } from "@/lib/errors";
import { formatInteger, formatShortDateTime } from "@/lib/format";
import { EVENT_RELATION_LABELS, VERDICT_LABELS } from "@/lib/labels";
import { checkPath } from "@/lib/links";
import type {
  EventDetail,
  EventLink,
  EventMember,
  GraphNode,
} from "@/lib/types";
import { guarded, useAdminData, type AdminAccess } from "./useAdminData";

const SOURCE_LABELS: Record<EventMember["source"], string> = {
  auto: "automat",
  llm: "model",
  review: "moderator",
  manual: "ręcznie",
};

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-line bg-surface">
      <h3 className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3 font-semibold">
        {title}
        {count !== undefined ? (
          <span className="inline-flex min-w-7 justify-center border border-line bg-subtle px-1.5 py-0.5 text-xs font-bold tabular-nums">
            {count}
          </span>
        ) : null}
      </h3>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function EventDetailPanel({
  access,
  eventId,
  events,
  onSelect,
  onChanged,
}: {
  access: AdminAccess;
  eventId: string;
  events: GraphNode[];
  onSelect: (id: string) => void;
  onChanged: () => void;
}) {
  const { state, reload, mutate } = useAdminData(
    access,
    `event:${eventId}`,
    (token, signal) => getEventDetail(token, eventId, signal),
  );
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);
  const [mergeSource, setMergeSource] = useState("");

  async function apply(
    action: () => Promise<EventDetail>,
    message: string,
    followNewEvent = false,
  ) {
    setBusy(true);
    setFeedback(null);
    try {
      const updated = await guarded(access, action());
      mutate(() => updated);
      if (followNewEvent && updated.event.id !== eventId) {
        onSelect(updated.event.id);
      }
      onChanged();
      setFeedback({ ok: true, text: message });
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się zapisać. ${describeError(error)}` });
    } finally {
      setBusy(false);
    }
  }

  async function actOnMember(member: EventMember, status: "accepted" | "rejected") {
    await apply(
      () =>
        reviewEventMember(access.token, eventId, member.id, {
          status,
          note: status === "rejected" ? "Odrzucono w panelu mapy" : null,
        }),
      status === "accepted"
        ? "Zaakceptowano przynależność do wydarzenia."
        : "Odrzucono propozycję; obserwacja trafiła do osobnego wydarzenia.",
      status === "rejected",
    );
  }

  async function splitMember(member: EventMember) {
    await apply(
      () => splitEventMember(access.token, eventId, member.id),
      "Wydzielono obserwację do nowego wydarzenia.",
      true,
    );
  }

  async function actOnLink(link: EventLink, status: "accepted" | "rejected") {
    setBusy(true);
    setFeedback(null);
    try {
      const updated = await guarded(
        access,
        reviewEventLink(access.token, link.id, { status }),
      );
      mutate((detail) => ({
        ...detail,
        links: detail.links.map((item) => (item.id === updated.id ? updated : item)),
      }));
      onChanged();
      setFeedback({
        ok: true,
        text: status === "accepted" ? "Zaakceptowano relację." : "Odrzucono relację.",
      });
    } catch (error) {
      setFeedback({ ok: false, text: `Nie udało się zapisać. ${describeError(error)}` });
    } finally {
      setBusy(false);
    }
  }

  if (state.status === "loading") return <LoadingBlock label="Wczytuję wydarzenie…" />;
  if (state.status === "error") return <ErrorBlock error={state.error} onRetry={reload} />;

  const detail = state.data;
  const event = detail.event;
  const proposed = detail.members.filter((member) => member.status === "proposed");
  const accepted = detail.members.filter((member) => member.status === "accepted");
  const others = events.filter((node) => node.kind === "event" && node.id !== eventId);
  const eventLabels = new Map(events.map((node) => [node.id, node.label]));

  return (
    <div className="space-y-4">
      <header className="rounded-xl border border-line-strong bg-subtle p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="eyebrow">Wydarzenie</p>
            <h2 className="mt-1 text-xl font-bold text-balance">{event.title}</h2>
            <p className="mt-1 text-sm text-muted">
              {formatInteger(event.member_count)} zaakceptowanych ·{" "}
              {formatInteger(event.proposed_count)} propozycji ·{" "}
              {formatInteger(event.anchors.length)} kotwic
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {event.risk === "high" ? (
              <Tag tone="warn" icon={ShieldAlert}>
                Wysokie ryzyko
              </Tag>
            ) : null}
            <Tag tone="info">{event.status === "active" ? "aktywne" : "scalone"}</Tag>
          </div>
        </div>
        {event.summary ? (
          <p className="mt-3 text-sm leading-relaxed text-ink-soft">{event.summary}</p>
        ) : null}
        <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <div className="flex gap-2">
            <dt className="text-muted">Publiczna etykieta:</dt>
            <dd className="font-medium">{event.public_label || "brak (poza mapą publiczną)"}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-muted">Pierwsze zgłoszenie:</dt>
            <dd className="font-medium">
              {formatShortDateTime(event.first_seen) ?? "brak daty"}
            </dd>
          </div>
        </dl>
        {event.keywords.length > 0 ? (
          <p className="mt-2 text-sm text-muted">{event.keywords.join(" · ")}</p>
        ) : null}
      </header>

      <div role="status" aria-live="polite">
        {feedback ? (
          <p
            className={`rounded-lg border px-4 py-3 font-medium ${
              feedback.ok
                ? "border-ok-line bg-ok-bg text-ok-fg"
                : "border-bad-line bg-bad-bg text-bad-fg"
            }`}
          >
            {feedback.text}
          </p>
        ) : null}
      </div>

      {proposed.length > 0 ? (
        <Section title="Kandydaci do decyzji" count={proposed.length}>
          <ul className="space-y-4">
            {proposed.map((member) => (
              <li key={member.id} className="border-b border-line pb-4 last:border-b-0 last:pb-0">
                <p className="font-medium">{member.claim_text}</p>
                <p className="mt-1 text-xs text-muted">
                  podobieństwo {member.score.toFixed(2)} · {SOURCE_LABELS[member.source]} ·{" "}
                  {formatShortDateTime(member.created_at) ?? "brak daty"}
                  {member.verdict ? ` · ${VERDICT_LABELS[member.verdict]}` : ""}
                </p>
                {member.reason ? (
                  <p className="mt-1 text-sm text-ink-soft">{member.reason}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    variant="primary"
                    disabled={busy}
                    onClick={() => void actOnMember(member, "accepted")}
                  >
                    Akceptuj
                  </Button>
                  <Button
                    variant="danger"
                    disabled={busy}
                    onClick={() => void actOnMember(member, "rejected")}
                  >
                    Odrzuć i wydziel
                  </Button>
                  <Link href={checkPath(member.check_id)} className="link inline-flex min-h-11 items-center gap-1 text-sm">
                    <ExternalLink aria-hidden="true" className="size-4" />
                    Otwórz analizę
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section title="Zaakceptowane obserwacje" count={accepted.length}>
        {accepted.length === 0 ? (
          <p className="text-muted">Brak zaakceptowanych obserwacji.</p>
        ) : (
          <ul className="space-y-4">
            {accepted.map((member) => (
              <li key={member.id} className="border-b border-line pb-4 last:border-b-0 last:pb-0">
                <p className="font-medium">{member.claim_text}</p>
                <p className="mt-1 text-xs text-muted">
                  {member.verdict ? VERDICT_LABELS[member.verdict] : "bez werdyktu"} ·{" "}
                  {SOURCE_LABELS[member.source]} · podobieństwo {member.score.toFixed(2)}
                  {member.reviewed_by ? ` · decyzja: ${member.reviewed_by}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-3">
                  <Link
                    href={checkPath(member.check_id)}
                    className="link inline-flex min-h-11 items-center gap-1 text-sm"
                  >
                    <ExternalLink aria-hidden="true" className="size-4" />
                    Otwórz analizę
                  </Link>
                  <Button
                    variant="quiet"
                    disabled={busy}
                    onClick={() => void splitMember(member)}
                  >
                    Wydziel do nowego wydarzenia
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Relacje z innymi wydarzeniami" count={detail.links.length}>
        {detail.links.length === 0 ? (
          <p className="text-muted">Brak relacji.</p>
        ) : (
          <ul className="space-y-4">
            {detail.links.map((link) => {
              const outgoing = link.src_event_id === eventId;
              const otherId = outgoing ? link.dst_event_id : link.src_event_id;
              return (
                <li key={link.id} className="border-b border-line pb-4 last:border-b-0 last:pb-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Tag
                      tone={
                        link.status === "accepted"
                          ? "info"
                          : link.status === "rejected"
                            ? "neutral"
                            : "warn"
                      }
                    >
                      {EVENT_RELATION_LABELS[link.relation]}
                    </Tag>
                    <span className="text-sm font-medium">
                      {outgoing ? "→" : "←"} {eventLabels.get(otherId) ?? otherId}
                    </span>
                    <span className="text-xs text-muted">
                      {link.score.toFixed(2)} ·{" "}
                      {link.status === "accepted"
                        ? "zaakceptowana"
                        : link.status === "rejected"
                          ? "odrzucona"
                          : "propozycja"}
                      {link.model ? ` · ${link.model}` : ""}
                    </span>
                  </div>
                  {link.reason ? (
                    <p className="mt-1 text-sm text-ink-soft">{link.reason}</p>
                  ) : null}
                  {link.evidence && Object.keys(link.evidence).length > 0 ? (
                    <dl className="mt-2 space-y-1 text-xs text-muted">
                      {Object.entries(link.evidence).map(([key, value]) => (
                        <div key={key} className="flex gap-1">
                          <dt>{key === "claim" ? "Zgłoszenie" : "Wydarzenie"}:</dt>
                          <dd className="italic">„{value}”</dd>
                        </div>
                      ))}
                    </dl>
                  ) : null}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      variant="primary"
                      disabled={busy || link.status === "accepted"}
                      onClick={() => void actOnLink(link, "accepted")}
                    >
                      Akceptuj relację
                    </Button>
                    <Button
                      variant="danger"
                      disabled={busy || link.status === "rejected"}
                      onClick={() => void actOnLink(link, "rejected")}
                    >
                      Odrzuć relację
                    </Button>
                    <Button variant="quiet" onClick={() => onSelect(otherId)}>
                      Pokaż powiązane wydarzenie
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Section>

      <Section title="Znane incydenty (kotwice)">
        {event.anchors.length === 0 ? (
          <p className="text-muted">Brak dopasowań do katalogu incydentów.</p>
        ) : (
          <ul className="space-y-3">
            {event.anchors.map((anchor) => (
              <li key={anchor.incident_id} className="border-b border-line pb-3 last:border-b-0 last:pb-0">
                <a href={anchor.url} target="_blank" rel="noreferrer" className="link font-medium">
                  {anchor.title}
                </a>
                <p className="text-xs text-muted">
                  {anchor.publisher}
                  {anchor.date ? ` · ${anchor.date}` : ""}
                </p>
                {anchor.note ? <p className="mt-1 text-sm text-ink-soft">{anchor.note}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Scal z innym wydarzeniem">
        {others.length === 0 ? (
          <p className="text-muted">Brak innych wydarzeń w widoku.</p>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            <label className="block min-w-60 flex-1 font-medium">
              Wydarzenie źródłowe
              <select
                value={mergeSource}
                onChange={(event) => setMergeSource(event.target.value)}
                className="mt-1 block min-h-11 w-full rounded-lg border border-line-strong bg-surface px-3"
              >
                <option value="">Wybierz wydarzenie…</option>
                {others.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.label} ({node.member_count})
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="secondary"
              disabled={busy || !mergeSource}
              onClick={() =>
                void apply(
                  () => mergeEvents(access.token, eventId, mergeSource),
                  "Scalono wydarzenia.",
                )
              }
            >
              Scal do tego wydarzenia
            </Button>
          </div>
        )}
        <p className="mt-2 text-xs text-muted">
          Scalanie przenosi obserwacje i kotwice do tego wydarzenia. Operacja jest zapisywana
          w audycie moderatora.
        </p>
      </Section>
    </div>
  );
}

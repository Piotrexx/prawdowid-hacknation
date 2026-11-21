"use client";

import {
  ArrowRight,
  Check,
  Compass,
  Copy,
  Info,
  Loader,
  MessageCircleQuestion,
  RotateCcw,
  ShieldAlert,
  TriangleAlert,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useId, useState, type ReactNode } from "react";
import { STATUS_TITLES } from "@/components/result/StatusPanel";
import { VerdictChip, verdictStripe } from "@/components/result/VerdictBadge";
import { warningCard } from "@/components/result/Warnings";
import { Button } from "@/components/ui/Button";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { Tag } from "@/components/ui/Tag";
import { cx } from "@/lib/cx";
import { formatTime, plural } from "@/lib/format";
import { STRENGTH_LABELS } from "@/lib/labels";
import { checkPath } from "@/lib/links";
import type { CheckResponse, ClaimResult, Evidence } from "@/lib/types";
import { describeFailure } from "./failure";

export type TurnState =
  | { kind: "loading" }
  | { kind: "result"; result: CheckResponse }
  | { kind: "failure"; error: unknown };

/** The assistant's side of the thread: a small mark, then the answer. */
function AssistantRow({ children }: { children: ReactNode }) {
  return (
    <div className="flex gap-3">
      <span
        aria-hidden="true"
        className="mt-1 hidden size-8 shrink-0 sm:grid place-items-center bg-accent text-sm font-bold text-on-accent"
      >
        P
      </span>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function Loading() {
  return (
    <AssistantRow>
      <div className="flex items-center gap-3 py-1.5">
        <Loader aria-hidden="true" className="size-5 text-accent motion-safe:animate-spin" />
        <div>
          <p className="font-semibold">Szukam w źródłach…</p>
          <p className="text-sm text-muted">Zwykle trwa to kilkanaście sekund.</p>
        </div>
      </div>
    </AssistantRow>
  );
}

function stanceCounts(evidence: Evidence[]) {
  const supports = evidence.filter((item) => item.stance === "supports").length;
  const refutes = evidence.filter((item) => item.stance === "refutes").length;
  return { supports, refutes, context: evidence.length - supports - refutes };
}

function ClaimSummary({
  claim,
  index,
  total,
}: {
  claim: ClaimResult;
  index: number;
  total: number;
}) {
  const counts = stanceCounts(claim.evidence);
  const sources = claim.evidence.slice(0, 2);
  const parts = [
    counts.supports ? `${counts.supports} potwierdza` : null,
    counts.refutes ? `${counts.refutes} przeczy` : null,
    counts.context ? `${counts.context} kontekst` : null,
  ].filter(Boolean);

  return (
    <li className={cx("border-l-4 px-5 py-4", verdictStripe(claim.verdict))}>
      {total > 1 ? (
        <p className="text-xs text-muted">
          Twierdzenie {index} z {total}
        </p>
      ) : null}
      <h3 className="font-semibold leading-snug">{claim.text}</h3>
      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <VerdictChip verdict={claim.verdict} uppercase />
        <span className="text-sm text-muted">
          Siła podstawy: {STRENGTH_LABELS[claim.strength.level] ?? claim.strength.level}
        </span>
        {claim.risk === "high" ? (
          <Tag tone="warn" icon={ShieldAlert}>
            Wysokie ryzyko
          </Tag>
        ) : null}
      </p>
      <p className="mt-2 line-clamp-3 text-[0.9375rem] leading-relaxed text-ink-soft">
        {claim.justification}
      </p>
      {claim.evidence.length > 0 ? (
        <div className="mt-2.5 text-sm">
          <p className="text-muted">
            {claim.evidence.length}{" "}
            {plural(claim.evidence.length, "materiał", "materiały", "materiałów")} ze źródeł
            {parts.length ? `: ${parts.join(", ")}` : ""}
          </p>
          <ul className="mt-1 flex flex-col gap-0.5">
            {sources.map((item) => (
              <li key={item.id}>
                <ExternalLink href={item.source.url} className="inline-block py-1">
                  {item.source.title || item.source.publisher}
                </ExternalLink>
                <span className="text-muted"> · {item.source.publisher}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-2.5 text-sm text-muted">Brak materiałów ze źródeł dla tego twierdzenia.</p>
      )}
    </li>
  );
}

function CopyLink({ id }: { id: string }) {
  const [state, setState] = useState<"idle" | "done" | "failed">("idle");
  async function copy() {
    try {
      await navigator.clipboard.writeText(new URL(checkPath(id), window.location.origin).href);
      setState("done");
    } catch {
      setState("failed");
    }
  }
  return (
    <>
      <Button onClick={copy}>
        {state === "done" ? (
          <Check aria-hidden="true" className="size-4.5" />
        ) : (
          <Copy aria-hidden="true" className="size-4.5" />
        )}
        {state === "done" ? "Skopiowano" : "Skopiuj link"}
      </Button>
      <span role="status" className="sr-only">
        {state === "done" ? "Skopiowano link do wyniku." : ""}
      </span>
      {state === "failed" ? (
        <p className="w-full text-sm text-muted">
          Nie udało się skopiować. Otwórz pełny wynik i skopiuj adres z paska przeglądarki.
        </p>
      ) : null}
    </>
  );
}

function Verdicts({ result }: { result: CheckResponse }) {
  const headingId = useId();
  const time = formatTime(result.created_at);
  const moderator = result.moderator_case;
  const notes = [
    ...(moderator.state === "recommended"
      ? [{ key: "mod", title: "Zalecamy ocenę przez człowieka", tone: "neutral" as const }]
      : moderator.state === "created" || moderator.state === "updated"
        ? [{ key: "mod", title: "Sprawa czeka na moderatora", tone: "info" as const }]
        : []),
    ...result.warnings.map((warning, index) => ({
      key: `${warning.code}-${index}`,
      title: `${warningCard(warning.code).title}. ${warning.message}`,
      tone: warningCard(warning.code).tone,
    })),
  ];

  return (
    <AssistantRow>
      <article aria-labelledby={headingId} className="border border-line bg-surface shadow-card">
        <header className="px-5 pt-4.5 pb-3.5">
          <h2 id={headingId} className="text-lg font-bold">
            Wynik sprawdzenia
          </h2>
          <p className="text-sm text-muted">
            {result.claims.length}{" "}
            {plural(result.claims.length, "twierdzenie", "twierdzenia", "twierdzeń")}
            {time ? ` · ${time}` : ""}
          </p>
          {result.summary ? (
            <p className="mt-3 leading-relaxed">
              <span className="font-semibold">W skrócie</span>{" "}
              <span className="text-muted">(interpretacja systemu)</span>: {result.summary}
            </p>
          ) : null}
        </header>

        {result.claims.length > 0 ? (
          <ol className="flex flex-col divide-y divide-line border-t border-line">
            {result.claims.map((claim, index) => (
              <ClaimSummary
                key={claim.id}
                claim={claim}
                index={index + 1}
                total={result.claims.length}
              />
            ))}
          </ol>
        ) : null}

        {notes.length > 0 ? (
          <section
            aria-label="Warto wiedzieć"
            className="border-t border-line bg-subtle px-5 py-3.5"
          >
            <ul className="flex flex-col gap-1.5 text-sm">
              {notes.map((note) => {
                const Icon = note.tone === "warn" || note.tone === "bad" ? TriangleAlert : Info;
                return (
                  <li key={note.key} className="flex gap-2">
                    <Icon
                      aria-hidden="true"
                      className={cx(
                        "mt-0.5 size-4 shrink-0",
                        note.tone === "warn"
                          ? "text-warn-fg"
                          : note.tone === "bad"
                            ? "text-bad-fg"
                            : "text-muted",
                      )}
                    />
                    {note.title}
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}

        <footer className="flex flex-wrap items-center gap-2 border-t border-line px-5 py-4">
          <Link
            href={checkPath(result.id)}
            className="inline-flex min-h-11 items-center gap-2 bg-accent px-4 font-semibold text-on-accent hover:bg-accent-hover"
          >
            Otwórz pełny wynik ze źródłami
            <ArrowRight aria-hidden="true" className="size-4.5" />
          </Link>
          <CopyLink id={result.id} />
        </footer>
      </article>
    </AssistantRow>
  );
}

const STATUS_ICONS: Record<string, LucideIcon> = {
  needs_clarification: MessageCircleQuestion,
  out_of_scope: Compass,
  error: Wrench,
};

const STATUS_FALLBACKS: Record<string, string> = {
  needs_clarification: "Nie wiem jeszcze, co dokładnie mam sprawdzić. Opisz to trochę szerzej.",
  out_of_scope: "Na to pytanie nie potrafię odpowiedzieć na podstawie moich źródeł.",
  error: "Coś poszło nie tak po stronie systemu. Spróbuj ponownie za chwilę.",
};

function StatusAnswer({
  result,
  onRetry,
  onFocusComposer,
}: {
  result: CheckResponse;
  onRetry: () => void;
  onFocusComposer: () => void;
}) {
  const Icon = STATUS_ICONS[result.status] ?? Wrench;
  const related = result.related_materials.slice(0, 3);

  return (
    <AssistantRow>
      <div className="border-2 border-dashed border-line-mid bg-surface px-5 py-4">
        <h2 className="flex items-center gap-2 font-bold">
          <Icon aria-hidden="true" className="size-5 text-muted" />
          {STATUS_TITLES[result.status] ?? STATUS_TITLES.error}
        </h2>
        <p className="mt-1.5 leading-relaxed whitespace-pre-line">
          {result.status_message || STATUS_FALLBACKS[result.status] || STATUS_FALLBACKS.error}
        </p>
        {result.status === "out_of_scope" ? (
          <p className="mt-1.5 text-sm text-muted">
            To nie jest ocena prawdziwości. Odpowiadam tylko na podstawie opisanego zbioru źródeł.
          </p>
        ) : null}
        {result.status === "error" ? (
          <p className="mt-1.5 text-sm text-muted">Ta treść nie została oceniona.</p>
        ) : null}

        {related.length > 0 ? (
          <div className="mt-3 text-sm">
            <p className="text-muted">Materiały, które mogą pomóc – oceń je samodzielnie:</p>
            <ul className="mt-1">
              {related.map((source) => (
                <li key={source.doc_id}>
                  <ExternalLink href={source.url} className="inline-block py-1">
                    {source.title || source.publisher}
                  </ExternalLink>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="mt-3.5 flex flex-wrap gap-2">
          {result.status === "needs_clarification" ? (
            <Button onClick={onFocusComposer}>Dopisz szczegóły poniżej</Button>
          ) : null}
          {result.status === "error" ? (
            <Button onClick={onRetry}>
              <RotateCcw aria-hidden="true" className="size-4.5" />
              Spróbuj ponownie
            </Button>
          ) : null}
        </div>
      </div>
    </AssistantRow>
  );
}

function FailureAnswer({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const failure = describeFailure(error);
  const Icon = failure.icon;
  return (
    <AssistantRow>
      <div className="border border-warn-line bg-warn-bg px-5 py-4">
        <h2 className="flex items-center gap-2 font-bold text-warn-fg">
          <Icon aria-hidden="true" className="size-5" />
          {failure.title}
        </h2>
        <p className="mt-1.5">{failure.message}</p>
        <p className="mt-1 text-sm text-ink-soft">To nie jest wynik sprawdzenia.</p>
        {failure.canRetry ? (
          <Button onClick={onRetry} className="mt-3">
            <RotateCcw aria-hidden="true" className="size-4.5" />
            Spróbuj ponownie
          </Button>
        ) : null}
      </div>
    </AssistantRow>
  );
}

interface ChatAnswerProps {
  state: TurnState;
  onRetry: () => void;
  onFocusComposer: () => void;
}

export function ChatAnswer({ state, onRetry, onFocusComposer }: ChatAnswerProps) {
  if (state.kind === "loading") return <Loading />;
  if (state.kind === "failure") return <FailureAnswer error={state.error} onRetry={onRetry} />;
  if (state.result.status === "completed") return <Verdicts result={state.result} />;
  return <StatusAnswer result={state.result} onRetry={onRetry} onFocusComposer={onFocusComposer} />;
}

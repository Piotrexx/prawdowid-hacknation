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
import { useTranslation } from "react-i18next";
import { STATUS_TITLES } from "@/components/result/StatusPanel";
import { VerdictChip, verdictStripe } from "@/components/result/VerdictBadge";
import { visibleWarnings, warningCard } from "@/components/result/Warnings";
import { Button } from "@/components/ui/Button";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { Tag } from "@/components/ui/Tag";
import { cx } from "@/lib/cx";
import { formatTime, plural } from "@/lib/format";
import { STRENGTH_LABELS } from "@/lib/labels";
import { checkPath } from "@/lib/links";
import type { CheckResponse, ClaimResult, ClarifyingQuestion, Evidence } from "@/lib/types";
import { describeFailure } from "./failure";

export type TurnState =
  | { kind: "loading" }
  | { kind: "result"; result: CheckResponse }
  | { kind: "failure"; error: unknown };

/** The assistant's side of the thread: a small mark in the margin, then the answer. */
function AssistantRow({ children }: { children: ReactNode }) {
  return (
    <div className="relative">
      <span
        aria-hidden="true"
        className="absolute top-1 right-full mr-3 hidden size-8 place-items-center bg-accent text-sm font-bold text-on-accent xl:grid"
      >
        P
      </span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function Loading() {
  const { t } = useTranslation();
  return (
    <AssistantRow>
      <div className="flex items-center gap-3 py-1.5">
        <Loader aria-hidden="true" className="size-5 text-accent motion-safe:animate-spin" />
        <div>
          <p className="font-semibold">{t("chat.searching")}</p>
          <p className="text-sm text-muted">{t("chat.usuallySeconds")}</p>
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
  const { t } = useTranslation();
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
        {state === "done" ? t("result.copied") : t("result.copyLink")}
      </Button>
      <span role="status" className="sr-only">
        {state === "done" ? t("result.copiedAria") : ""}
      </span>
      {state === "failed" ? (
        <p className="w-full text-sm text-muted">
          {t("result.copyFailed")}
        </p>
      ) : null}
    </>
  );
}

function Verdicts({ result }: { result: CheckResponse }) {
  const { t } = useTranslation();
  const headingId = useId();
  const time = formatTime(result.created_at);
  const moderator = result.moderator_case;
  const notes = [
    ...(moderator.state === "recommended"
      ? [{ key: "mod", title: t("result.humanReview"), tone: "neutral" as const }]
      : moderator.state === "created" || moderator.state === "updated"
        ? [{ key: "mod", title: t("result.waitingModerator"), tone: "info" as const }]
        : []),
    ...visibleWarnings(result.warnings).map((warning, index) => ({
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
            {t("result.title")}
          </h2>
          <p className="text-sm text-muted">
            {result.claims.length}{" "}
            {plural(result.claims.length, "twierdzenie", "twierdzenia", "twierdzeń")}
            {time ? ` · ${time}` : ""}
          </p>
          {result.summary ? (
            <p className="mt-3 leading-relaxed">
              <span className="font-semibold">{t("result.summary")}</span>{" "}
              <span className="text-muted">{t("result.systemNote")}</span>: {result.summary}
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
            {t("result.openFull")}
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

interface ClarificationActions {
  /** A later turn already answers this question. */
  answered: boolean;
  /** Another check is running, so a quick answer cannot be sent yet. */
  busy: boolean;
  /** Ties the composer to this question and focuses it. */
  onReply: () => void;
  /** Sends the answer to all questions as one reply. */
  onAnswer: (text: string) => void;
}

/** One reply for every question, so the model thinks again only once. */
function composeAnswer(questions: ClarifyingQuestion[], answers: string[]): string {
  if (questions.length === 1) return answers[0];
  return questions
    .flatMap((question, index) => (answers[index] ? [`${question.text} – ${answers[index]}`] : []))
    .join("\n");
}

/**
 * Each question takes a ready option or a typed answer; nothing is sent until "Wyślij odpowiedzi",
 * so the user can answer all of them first. Unanswered questions are simply left out.
 */
function ClarificationForm({
  questions,
  clarify,
}: {
  questions: ClarifyingQuestion[];
  clarify: ClarificationActions;
}) {
  const { t } = useTranslation();
  const baseId = useId();
  const [picked, setPicked] = useState<string[]>(() => questions.map(() => ""));
  const [typed, setTyped] = useState<string[]>(() => questions.map(() => ""));
  const answers = questions.map((_, index) => typed[index].trim() || picked[index]);
  const count = answers.filter(Boolean).length;
  const total = questions.length;

  function set(list: string[], index: number, value: string): string[] {
    return list.map((item, i) => (i === index ? value : item));
  }

  function pick(index: number, option: string) {
    setPicked((list) => set(list, index, list[index] === option ? "" : option));
    setTyped((list) => set(list, index, ""));
  }

  function type(index: number, value: string) {
    setTyped((list) => set(list, index, value));
    if (value.trim()) setPicked((list) => set(list, index, ""));
  }

  return (
    <form
      noValidate
      className="mt-2.5"
      onSubmit={(event) => {
        event.preventDefault();
        if (count > 0 && !clarify.busy) clarify.onAnswer(composeAnswer(questions, answers));
      }}
    >
      <ol className={cx("flex flex-col gap-4", total > 1 && "list-decimal pl-5")}>
        {questions.map((question, index) => {
          const labelId = `${baseId}-q${index}`;
          return (
            <li key={index} className="leading-relaxed">
              <p id={labelId} className="font-semibold">
                {question.text}
              </p>
              {question.options.length > 0 ? (
                <div role="group" aria-labelledby={labelId} className="mt-1.5 flex flex-wrap gap-2">
                  {question.options.map((option) => {
                    const pressed = picked[index] === option;
                    return (
                      <button
                        key={option}
                        type="button"
                        aria-pressed={pressed}
                        onClick={() => pick(index, option)}
                        className={cx(
                          "inline-flex min-h-11 items-center gap-1.5 border px-3.5 text-sm font-semibold",
                          pressed
                            ? "border-accent bg-info-bg text-accent"
                            : "border-line-strong bg-surface hover:border-accent hover:bg-subtle",
                        )}
                      >
                        {pressed ? <Check aria-hidden="true" className="size-4" /> : null}
                        {option}
                      </button>
                    );
                  })}
                </div>
              ) : null}
              <input
                type="text"
                value={typed[index]}
                aria-labelledby={labelId}
                maxLength={500}
                placeholder={
                  question.options.length > 0 ? t("status.clarifyOther") : t("status.clarifyPlaceholder")
                }
                onChange={(event) => type(index, event.target.value)}
                className="mt-1.5 block min-h-11 w-full border border-line-strong bg-surface px-3 text-base placeholder:text-muted focus:border-accent focus:outline-none"
              />
            </li>
          );
        })}
      </ol>
      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        <Button type="submit" variant="primary" disabled={count === 0 || clarify.busy}>
          {total > 1 && count < total
            ? t("status.clarifySubmitCount", { count, total })
            : t("status.clarifySubmit")}
        </Button>
        <Button variant="quiet" onClick={clarify.onReply}>
          {t("status.clarifyFreeText")}
        </Button>
      </div>
    </form>
  );
}

function StatusAnswer({
  result,
  onRetry,
  clarify,
}: {
  result: CheckResponse;
  onRetry: () => void;
  clarify: ClarificationActions;
}) {
  const { t } = useTranslation();
  const Icon = STATUS_ICONS[result.status] ?? Wrench;
  const clarification = result.status === "needs_clarification" ? result.clarification : null;
  const questions = clarification?.questions ?? [];
  const asking = questions.length > 0 && !clarify.answered;
  const related = result.related_materials.slice(0, 3);
  const statusTitleKey = `status.${result.status}` as const;
  const statusFallbackKey = `status.${result.status}_fallback` as const;

  return (
    <AssistantRow>
      <div className="border-2 border-dashed border-line-mid bg-surface px-5 py-4">
        <h2 className="flex items-center gap-2 font-bold">
          <Icon aria-hidden="true" className="size-5 text-muted" />
          {STATUS_TITLES[result.status] ?? STATUS_TITLES.error}
        </h2>
        {questions.length > 0 ? (
          <>
            <p className="mt-1.5 leading-relaxed">{t("status.clarifyIntro")}</p>
            {asking ? (
              <ClarificationForm key={result.id} questions={questions} clarify={clarify} />
            ) : (
              <ol className={cx("mt-2.5 flex flex-col gap-3", questions.length > 1 && "list-decimal pl-5")}>
                {questions.map((question, index) => (
                  <li key={index} className="leading-relaxed font-semibold">
                    {question.text}
                  </li>
                ))}
              </ol>
            )}
            {clarification && clarification.max_rounds > 1 && clarification.round > 1 ? (
              <p className="mt-2.5 text-sm text-muted">
                {t("status.clarifyRound", { round: clarification.round, max: clarification.max_rounds })}
              </p>
            ) : null}
          </>
        ) : (
          <p className="mt-1.5 leading-relaxed whitespace-pre-line">
            {result.status_message || t(statusFallbackKey) || t("status.error_fallback")}
          </p>
        )}
        {result.status === "out_of_scope" ? (
          <p className="mt-1.5 text-sm text-muted">
            {t("status.out_of_scope_note")}
          </p>
        ) : null}
        {result.status === "error" ? (
          <p className="mt-1.5 text-sm text-muted">{t("status.error_note")}</p>
        ) : null}

        {related.length > 0 ? (
          <div className="mt-3 text-sm">
            <p className="text-muted">{t("result.relatedMaterials")}</p>
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
            clarify.answered ? (
              <p className="text-sm text-muted">{t("status.clarifyAnswered")}</p>
            ) : asking ? null : (
              <Button onClick={clarify.onReply}>{t("status.clarify")}</Button>
            )
          ) : null}
          {result.status === "error" ? (
            <Button onClick={onRetry}>
              <RotateCcw aria-hidden="true" className="size-4.5" />
              {t("status.retry")}
            </Button>
          ) : null}
        </div>
      </div>
    </AssistantRow>
  );
}

function FailureAnswer({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const { t } = useTranslation();
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
        <p className="mt-1 text-sm text-ink-soft">{t("status.notResult")}</p>
        {failure.canRetry ? (
          <Button onClick={onRetry} className="mt-3">
            <RotateCcw aria-hidden="true" className="size-4.5" />
            {t("status.retry")}
          </Button>
        ) : null}
      </div>
    </AssistantRow>
  );
}

interface ChatAnswerProps extends ClarificationActions {
  state: TurnState;
  onRetry: () => void;
}

export function ChatAnswer({ state, onRetry, ...clarify }: ChatAnswerProps) {
  if (state.kind === "loading") return <Loading />;
  if (state.kind === "failure") return <FailureAnswer error={state.error} onRetry={onRetry} />;
  if (state.result.status === "completed") return <Verdicts result={state.result} />;
  return <StatusAnswer result={state.result} onRetry={onRetry} clarify={clarify} />;
}

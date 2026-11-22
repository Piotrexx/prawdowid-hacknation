"use client";

import { EyeOff, Quote, Scale } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useImageAttachment } from "@/components/check/useImageAttachment";
import { ApiError, createCheck, createImageCheck, isAbort } from "@/lib/api";
import { cx } from "@/lib/cx";
import { describeError } from "@/lib/errors";
import { plural } from "@/lib/format";
import { rememberCheck } from "@/lib/history";
import { SHORT_VERDICT_LABELS } from "@/lib/labels";
import { isSingleUrl } from "@/lib/links";
import { useNewCheckCount } from "@/lib/newCheck";
import { cacheResult } from "@/lib/resultCache";
import { ensureSessionId } from "@/lib/session";
import type { CheckResponse } from "@/lib/types";
import { ChatAnswer } from "./ChatAnswer";
import { Composer, TEXT_LIMIT } from "./Composer";
import {
  addTurn,
  openConversation,
  reloadResult,
  saveScroll,
  savedScroll,
  trackRequest,
  updateTurn,
  useTurns,
  type Turn,
} from "./conversationStore";

function announce(result: CheckResponse, t: ReturnType<typeof import("react-i18next").useTranslation>["t"]): string {
  if (result.status !== "completed")
    return result.status_message || "Nie udało się ocenić tej treści.";
  const verdicts = result.claims.map(
    (claim) => SHORT_VERDICT_LABELS[claim.verdict] ?? claim.verdict,
  );
  const count = result.claims.length;
  const countKey = count === 1 ? "chat.resultReady" : count < 5 ? "chat.resultReady_few" : "chat.resultReady_many";
  return t(countKey, { count, verdicts: verdicts.join(", ") });
}

function UserMessage({ turn }: { turn: Turn }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const long = turn.text.length > 400 || turn.text.split("\n").length > 6;
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] bg-subtle px-4.5 py-3 sm:max-w-[75%]">
        <h2 className="sr-only">{t("chat.myMessage")}</h2>
        {turn.imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- local object URL preview
          <img
            src={turn.imageUrl}
            alt="Dołączony zrzut ekranu"
            className="mb-2 max-h-48 border border-line object-contain"
          />
        ) : turn.image ? (
          <p className="text-sm text-muted">Przesłane zdjęcie (podgląd nie jest zapisywany)</p>
        ) : null}
        {turn.image ? null : (
          <>
            <p
              className={cx(
                "leading-relaxed break-words whitespace-pre-line",
                long && !expanded && "line-clamp-6",
              )}
            >
              {turn.text}
            </p>
            {long ? (
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => setExpanded((value) => !value)}
                className="link mt-1 inline-flex min-h-11 items-center text-sm font-semibold"
              >
                {expanded ? t("chat.collapse") : t("chat.expand")}
              </button>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

/** Emphasis only, not a link: the accent colour marks what can be pasted. */
function Highlight({ children }: { children: ReactNode }) {
  return (
    <strong className="font-semibold text-accent">
      {children}
    </strong>
  );
}

function Welcome({ title }: { title: ReactNode }) {
  const { t } = useTranslation();
  const facts = [
    { icon: EyeOff, text: t("welcome.privacy") },
    { icon: Quote, text: t("welcome.quotes") },
    { icon: Scale, text: t("welcome.judgment") },
  ];
  return (
    <div className="flex flex-1 flex-col justify-center py-10">
      {title}
      <span aria-hidden="true" className="title-rule my-5" />
      <p className="text-lg leading-relaxed text-ink-soft">
        Wklej <Highlight>{t("nav.check").toLowerCase() === "sprawdź" ? "wiadomość" : "wiadomość"}</Highlight>, <Highlight>link</Highlight> albo{" "}
        <Highlight>zrzut ekranu</Highlight>. Zobaczysz, co mówią o tym źródła i czego nie udało się
        ustalić.
      </p>
      <ul className="mt-8 grid gap-3 sm:grid-cols-3">
        {facts.map(({ icon: Icon, text }) => (
          <li key={text} className="flex gap-3 border border-line px-4 py-3.5 text-sm sm:flex-col">
            <Icon aria-hidden="true" className="size-5 shrink-0 text-accent" />
            {text}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Conversation({ focusOnMount }: { focusOnMount: boolean }) {
  const { t } = useTranslation();
  const turns = useTurns();
  const [text, setText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [waitSeconds, setWaitSeconds] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const image = useImageAttachment();

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const turnRefs = useRef(new Map<number, HTMLDivElement>());
  const retryAt = useRef(0);
  const scrollTo = useRef<number | null>(null);
  const scrollToResult = useRef<string | null>(null);

  const busy = turns.some((turn) => turn.state.kind === "loading");
  const waiting = waitSeconds > 0;

  // "Wróć do czatu" links here with ?rozmowa=<conversation>&wynik=<check>: reopen that conversation
  // and show the message that asked for the check. A plain "back" returns to the last position.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const conversation = params.get("rozmowa");
    let frame = 0;
    if (conversation) {
      window.history.replaceState(null, "", "/");
      if (openConversation(conversation)) scrollToResult.current = params.get("wynik");
    } else {
      const y = savedScroll();
      if (y > 0) frame = requestAnimationFrame(() => window.scrollTo(0, y));
    }
    return () => {
      cancelAnimationFrame(frame);
      saveScroll(window.scrollY);
    };
  }, []);

  // Results above the target load one by one and change its position, so keep it in view
  // until every reopened result has arrived.
  useEffect(() => {
    const target = scrollToResult.current;
    if (!target) return;
    const turn = turns.find((item) => item.resultId === target);
    if (!turn) return;
    turnRefs.current.get(turn.id)?.scrollIntoView({ block: "start" });
    if (!turns.some((item) => item.state.kind === "loading")) scrollToResult.current = null;
  }, [turns]);

  useEffect(() => {
    if (focusOnMount) textareaRef.current?.focus();
  }, [focusOnMount]);

  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => {
      setWaitSeconds(Math.max(0, Math.ceil((retryAt.current - Date.now()) / 1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [waiting]);

  // A sent message moves to the top of the screen, leaving room for the answer below it.
  useEffect(() => {
    const id = scrollTo.current;
    if (id === null) return;
    scrollTo.current = null;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    turnRefs.current
      .get(id)
      ?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }, [turns]);

  async function run(id: number, payload: { text: string; file: File | null }) {
    const controller = new AbortController();
    const untrack = trackRequest(controller);
    updateTurn(id, { kind: "loading" });
    setStatus(t("chat.checkingStatus"));
    try {
      const sessionId = ensureSessionId();
      const result = payload.file
        ? await createImageCheck(payload.file, sessionId, controller.signal)
        : await createCheck(
            isSingleUrl(payload.text)
              ? { url: payload.text, session_id: sessionId }
              : { text: payload.text, session_id: sessionId },
            controller.signal,
          );
      if (result.status === "completed") {
        cacheResult(result);
        rememberCheck(result);
      }
      // A question about an image can only be answered in text, so hand the read text back.
      if (result.status === "needs_clarification" && payload.file && result.input.text.trim()) {
        setText(result.input.text);
      }
      updateTurn(id, { kind: "result", result });
      setStatus(announce(result, t));
    } catch (error) {
      if (isAbort(error)) return;
      if (error instanceof ApiError && error.kind === "rate_limit") {
        const seconds = error.retryAfterSeconds ?? 0;
        retryAt.current = Date.now() + seconds * 1000;
        setWaitSeconds(seconds);
      }
      updateTurn(id, { kind: "failure", error });
      setStatus(`Nie udało się sprawdzić. ${describeError(error)}`);
    } finally {
      untrack();
    }
  }

  function send() {
    if (busy || waiting) return;
    const trimmed = text.trim();
    const file = image.attachment?.file ?? null;
    if (!file && !trimmed) {
      setFormError(t("composer.errorEmpty"));
      textareaRef.current?.focus();
      return;
    }
    if (!file && trimmed.length > TEXT_LIMIT) {
      setFormError(t("composer.errorTooLong"));
      textareaRef.current?.focus();
      return;
    }
    setFormError(null);

    const id = addTurn(trimmed, file);
    scrollTo.current = id;
    setText("");
    image.clear();
    textareaRef.current?.focus();
    void run(id, { text: trimmed, file });
  }

  function retry(turn: Turn) {
    if (busy || waiting) return;
    // A reopened message already has a check on the backend: load it again rather than re-check.
    if (turn.resultId) reloadResult(turn.id);
    else void run(turn.id, { text: turn.text, file: turn.file });
  }

  function focusComposer() {
    const field = textareaRef.current;
    if (!field) return;
    field.focus();
    field.setSelectionRange(field.value.length, field.value.length);
  }

  function hasFiles(event: DragEvent) {
    return Array.from(event.dataTransfer.types).includes("Files");
  }

  const title = (
    <h1
      id="powitanie"
      className={
        turns.length > 0
          ? "sr-only"
          : "text-[1.75rem] leading-tight font-bold tracking-[-0.01em] sm:text-[2.25rem]"
      }
    >
      {t("welcome.title")}
    </h1>
  );

  return (
    <div
      className={cx(
        "flex min-w-0 flex-1 flex-col",
        dragActive && "outline-3 -outline-offset-8 outline-focus outline-dashed",
      )}
      onDragOver={(event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragActive(false);
      }}
      onDrop={(event) => {
        if (!hasFiles(event)) return;
        event.preventDefault();
        setDragActive(false);
        const file = event.dataTransfer.files[0];
        if (file) image.attach(file);
      }}
    >
      <div className="mx-auto flex w-full max-w-[50rem] flex-1 flex-col px-5 sm:px-8">
        {turns.length === 0 ? (
          <Welcome title={title} />
        ) : (
          <>
            {title}
            <section aria-label="Rozmowa" className="flex flex-1 flex-col gap-6 py-8">
              {turns.map((turn) => (
                <div
                  key={turn.id}
                  ref={(element) => {
                    if (element) turnRefs.current.set(turn.id, element);
                    else turnRefs.current.delete(turn.id);
                  }}
                  className="flex scroll-mt-6 flex-col gap-4"
                >
                  <UserMessage turn={turn} />
                  <ChatAnswer
                    state={turn.state}
                    onRetry={() => retry(turn)}
                    onFocusComposer={focusComposer}
                  />
                </div>
              ))}
              {/* Leaves room so the newest message can scroll to the top of the screen. */}
              <div aria-hidden="true" className="min-h-[40vh]" />
            </section>
          </>
        )}

        <p role="status" className="sr-only">
          {status}
        </p>

        <Composer
          text={text}
          onTextChange={(value) => {
            setText(value);
            if (formError) setFormError(null);
          }}
          attachment={image.attachment}
          imageError={image.error}
          onPickImage={image.attach}
          onClearImage={image.clear}
          onSubmit={send}
          busy={busy}
          error={formError}
          waitSeconds={waitSeconds}
          textareaRef={textareaRef}
        />
      </div>
    </div>
  );
}

/** The home page: a conversation that "Nowa sesja" in the sidebar starts afresh. */
export function ChatView() {
  const count = useNewCheckCount();
  return <Conversation key={count} focusOnMount={count > 0} />;
}

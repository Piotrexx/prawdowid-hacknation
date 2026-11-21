"use client";

import {
  Clock,
  FileWarning,
  RotateCcw,
  WifiOff,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CheckResult } from "@/components/result/CheckResult";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/Notice";
import { ApiError, createCheck, createImageCheck, isAbort } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { isSingleUrl } from "@/lib/links";
import { ensureSessionId } from "@/lib/session";
import type { CheckResponse } from "@/lib/types";
import { BusyPanel } from "./BusyPanel";
import { CheckForm, TEXT_LIMIT, isExampleOnly } from "./CheckForm";
import { Permalink } from "./Permalink";
import { SessionControls } from "./SessionControls";
import { useImageAttachment } from "./useImageAttachment";

type Phase =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "result"; result: CheckResponse }
  | { kind: "failure"; error: unknown };

function validate(text: string, hasImage: boolean): string | null {
  if (hasImage) return null;
  if (!text.trim()) {
    return "Wpisz lub wklej treść, którą chcesz sprawdzić. Możesz też dodać zrzut ekranu.";
  }
  if (isExampleOnly(text)) {
    return "Wklej pod pytaniem treść, którą chcesz sprawdzić.";
  }
  if (text.length > TEXT_LIMIT) {
    return "Tekst jest za długi. Skróć go i spróbuj ponownie.";
  }
  return null;
}

interface Failure {
  icon: LucideIcon;
  title: string;
  message: string;
  canRetry: boolean;
}

function describeFailure(error: unknown): Failure {
  const kind = error instanceof ApiError ? error.kind : "http";
  const message = describeError(error);
  if (kind === "rate_limit") {
    return { icon: Clock, title: "Za dużo sprawdzeń naraz", message, canRetry: false };
  }
  if (kind === "validation") {
    return {
      icon: FileWarning,
      title: "Nie udało się przyjąć tej treści",
      message,
      canRetry: false,
    };
  }
  if (kind === "network" || kind === "timeout") {
    return { icon: WifiOff, title: "Problem z połączeniem", message, canRetry: true };
  }
  return { icon: Wrench, title: "Problem po stronie serwera", message, canRetry: true };
}

export function CheckFlow() {
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const [waitSeconds, setWaitSeconds] = useState(0);
  const image = useImageAttachment();

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const busyRef = useRef<HTMLDivElement>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement>(null);
  const failureRef = useRef<HTMLDivElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const focusedPhaseRef = useRef<Phase>(phase);
  const retryAtRef = useRef(0);

  const busy = phase.kind === "loading";
  const waiting = waitSeconds > 0;

  useEffect(() => {
    // Effects also re-run when the router shows this page again; move focus only on a real change.
    if (focusedPhaseRef.current === phase) return;
    focusedPhaseRef.current = phase;
    if (phase.kind === "loading") busyRef.current?.focus();
    if (phase.kind === "result") resultHeadingRef.current?.focus();
    if (phase.kind === "failure") failureRef.current?.focus();
  }, [phase]);

  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => {
      setWaitSeconds(Math.max(0, Math.ceil((retryAtRef.current - Date.now()) / 1000)));
    }, 1000);
    return () => clearInterval(timer);
  }, [waiting]);

  async function submit() {
    if (busy || waiting) return;
    const problem = validate(text, image.attachment !== null);
    if (problem) {
      setFormError(problem);
      textareaRef.current?.focus();
      return;
    }
    setFormError(null);

    const controller = new AbortController();
    requestRef.current = controller;
    setPhase({ kind: "loading" });

    try {
      const sessionId = ensureSessionId();
      const trimmed = text.trim();
      const file = image.attachment?.file;
      const result = file
        ? await createImageCheck(file, sessionId, controller.signal)
        : await createCheck(
            isSingleUrl(trimmed)
              ? { url: trimmed, session_id: sessionId }
              : { text: trimmed, session_id: sessionId },
            controller.signal,
          );

      // A question about an image can only be answered in text, so hand the read text back.
      if (result.status === "needs_clarification" && file && result.input.text.trim()) {
        setText(result.input.text);
        image.clear();
      }
      setPhase({ kind: "result", result });
    } catch (error) {
      if (isAbort(error)) return;
      if (error instanceof ApiError && error.kind === "rate_limit") {
        const seconds = error.retryAfterSeconds ?? 0;
        retryAtRef.current = Date.now() + seconds * 1000;
        setWaitSeconds(seconds);
      }
      setPhase({ kind: "failure", error });
    }
  }

  function reset() {
    requestRef.current?.abort();
    setText("");
    image.clear();
    setFormError(null);
    setPhase({ kind: "idle" });
  }

  function startOver() {
    reset();
    textareaRef.current?.focus();
  }

  function focusInput() {
    const field = textareaRef.current;
    if (!field) return;
    field.focus();
    field.setSelectionRange(field.value.length, field.value.length);
  }

  const result = phase.kind === "result" ? phase.result : null;
  const failure = phase.kind === "failure" ? describeFailure(phase.error) : null;

  return (
    <div className="space-y-8">
      <CheckForm
        text={text}
        onTextChange={(value) => {
          setText(value);
          if (formError) setFormError(null);
        }}
        attachment={image.attachment}
        imageError={image.error}
        onPickImage={image.attach}
        onClearImage={image.clear}
        onSubmit={submit}
        busy={busy}
        error={formError}
        waitSeconds={waitSeconds}
        textareaRef={textareaRef}
      />

      <div aria-live="polite" aria-busy={busy} className="space-y-6">
        {busy ? <BusyPanel panelRef={busyRef} /> : null}

        {failure ? (
          <div ref={failureRef} tabIndex={-1} className="space-y-3">
            <Notice icon={failure.icon} title={failure.title}>
              <p>{failure.message}</p>
              <p className="text-muted">
                To nie jest wynik sprawdzenia. Twoja treść została w polu powyżej.
              </p>
            </Notice>
            {failure.canRetry ? (
              <Button onClick={submit}>
                <RotateCcw aria-hidden="true" className="size-5" />
                Spróbuj ponownie
              </Button>
            ) : null}
          </div>
        ) : null}

        {result ? (
          <>
            <CheckResult
              result={result}
              headingRef={resultHeadingRef}
              statusActions={
                result.status === "needs_clarification" ? (
                  <div className="space-y-3">
                    <p>Dopisz szczegóły w polu powyżej i wybierz „Sprawdź”.</p>
                    <Button onClick={focusInput}>Wróć do pola z treścią</Button>
                  </div>
                ) : result.status === "error" ? (
                  <Button onClick={submit}>
                    <RotateCcw aria-hidden="true" className="size-5" />
                    Spróbuj ponownie
                  </Button>
                ) : null
              }
            />
            {result.status === "completed" ? <Permalink id={result.id} /> : null}
            <Button variant="primary" onClick={startOver}>
              Sprawdź coś innego
            </Button>
          </>
        ) : null}
      </div>

      <SessionControls onDeleted={reset} />
    </div>
  );
}

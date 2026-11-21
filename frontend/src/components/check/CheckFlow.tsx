"use client";

import { Clock, FileWarning, RotateCcw, WifiOff, Wrench, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CheckResult } from "@/components/result/CheckResult";
import { Button } from "@/components/ui/Button";
import { Notice } from "@/components/ui/Notice";
import { ApiError, createCheck, isAbort } from "@/lib/api";
import { describeError } from "@/lib/errors";
import { ensureSessionId } from "@/lib/session";
import type { CheckResponse } from "@/lib/types";
import { BusyPanel } from "./BusyPanel";
import { CheckForm } from "./CheckForm";
import { Permalink } from "./Permalink";

type Phase =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "result"; result: CheckResponse }
  | { kind: "failure"; error: unknown };

function validate(url: string): string | null {
  if (!url.trim()) {
    return "Wklej link do artykułu, który chcesz sprawdzić.";
  }
  if (!isValidUrl(url)) {
    return "To nie wygląda na poprawny adres URL (musi zaczynać się od http:// lub https://).";
  }
  return null;
}

function isValidUrl(text: string): boolean {
  try {
    const url = new URL(text.trim());
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
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
      title: "Nie udało się przyjąć tego linku",
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
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const [waitSeconds, setWaitSeconds] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const busyRef = useRef<HTMLDivElement>(null);
  const resultHeadingRef = useRef<HTMLHeadingElement>(null);
  const failureRef = useRef<HTMLDivElement>(null);
  const requestRef = useRef<AbortController | null>(null);
  const focusedPhaseRef = useRef<Phase>(phase);
  const retryAtRef = useRef(0);

  const busy = phase.kind === "loading";
  const waiting = waitSeconds > 0;

  useEffect(() => {
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
    const problem = validate(url);
    if (problem) {
      setFormError(problem);
      inputRef.current?.focus();
      return;
    }
    setFormError(null);

    const controller = new AbortController();
    requestRef.current = controller;
    setPhase({ kind: "loading" });

    try {
      const sessionId = ensureSessionId();
      const result = await createCheck({ url: url.trim(), session_id: sessionId }, controller.signal);
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
    setUrl("");
    setFormError(null);
    setPhase({ kind: "idle" });
  }

  function startOver() {
    reset();
    inputRef.current?.focus();
  }

  const result = phase.kind === "result" ? phase.result : null;
  const failure = phase.kind === "failure" ? describeFailure(phase.error) : null;

  return (
    <div className="space-y-8">
      <CheckForm
        url={url}
        onUrlChange={(value) => {
          setUrl(value);
          if (formError) setFormError(null);
        }}
        onSubmit={submit}
        busy={busy}
        error={formError}
        waitSeconds={waitSeconds}
        inputRef={inputRef}
      />

      <div aria-live="polite" aria-busy={busy} className="space-y-6">
        {busy ? <BusyPanel panelRef={busyRef} /> : null}

        {failure ? (
          <div ref={failureRef} tabIndex={-1} className="space-y-3">
            <Notice icon={failure.icon} title={failure.title}>
              <p>{failure.message}</p>
              <p className="text-muted">
                To nie jest wynik sprawdzenia. Twój link został w polu powyżej.
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
                    <p>Sprawdź, czy link jest poprawny, i spróbuj ponownie.</p>
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
              Sprawdź inny artykuł
            </Button>
          </>
        ) : null}
      </div>
    </div>
  );
}
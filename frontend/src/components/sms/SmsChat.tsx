"use client";

import { RefreshCw, Send } from "lucide-react";
import {
  useEffect,
  useEffectEvent,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
} from "react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { ApiError, getSmsThread, isAbort, sendSms } from "@/lib/api";
import { describeError } from "@/lib/errors";
import type { SmsMessage, SmsThread } from "@/lib/types";
import { BubbleFrame, SmsBubble } from "./SmsBubble";

const POLL_MS = 2000;
// How long to keep polling for a reply, and for follow-up parts once a reply has arrived.
const REPLY_WINDOW_MS = 90_000;
const SETTLE_WINDOW_MS = 15_000;

type ThreadStatus = "loading" | "ready" | "demo_off" | "error";

function subscribeToVisibility(onChange: () => void) {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
}

function useTabVisible(): boolean {
  return useSyncExternalStore(
    subscribeToVisibility,
    () => document.visibilityState === "visible",
    () => true,
  );
}

export function SmsChat({ phone }: { phone: string }) {
  const [status, setStatus] = useState<ThreadStatus>("loading");
  const [messages, setMessages] = useState<SmsMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [awaitingReply, setAwaitingReply] = useState(false);
  const [polling, setPolling] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const visible = useTabVisible();

  const logRef = useRef<HTMLDivElement>(null);
  const draftRef = useRef<HTMLTextAreaElement>(null);
  const fetchingRef = useRef(false);
  const newestReplyRef = useRef(0);
  const pollUntilRef = useRef(0);

  const sending = pending !== null;

  function showThread(thread: SmsThread) {
    setMessages(thread.messages);
    setStatus("ready");
    setProblem(null);
    const newestReply = thread.messages
      .filter((message) => message.direction === "out")
      .reduce((newest, message) => Math.max(newest, message.id), 0);
    if (newestReply > newestReplyRef.current) {
      newestReplyRef.current = newestReply;
      setAwaitingReply(false);
      pollUntilRef.current = Date.now() + SETTLE_WINDOW_MS;
    }
  }

  function showFailure(error: unknown) {
    if (isAbort(error)) return;
    if (error instanceof ApiError && error.kind === "not_found") {
      setStatus("demo_off");
      setPolling(false);
      return;
    }
    setStatus((current) => (current === "loading" ? "error" : current));
    setProblem(describeError(error));
  }

  async function refresh() {
    if (fetchingRef.current) return;
    fetchingRef.current = true;
    try {
      showThread(await getSmsThread(phone));
    } catch (error) {
      showFailure(error);
    } finally {
      fetchingRef.current = false;
    }
  }

  const onThread = useEffectEvent(showThread);
  const onFailure = useEffectEvent(showFailure);

  const pollTick = useEffectEvent(() => {
    if (Date.now() > pollUntilRef.current) {
      setPolling(false);
      return;
    }
    void refresh();
  });

  useEffect(() => {
    const controller = new AbortController();
    getSmsThread(phone, controller.signal).then(onThread, onFailure);
    return () => controller.abort();
  }, [phone]);

  useEffect(() => {
    if (!polling || !visible) return;
    const timer = setInterval(pollTick, POLL_MS);
    return () => clearInterval(timer);
  }, [polling, visible]);

  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages.length, pending, awaitingReply]);

  async function send() {
    const body = draft.trim();
    if (!body || sending || status === "demo_off") return;
    setPending(body);
    setDraft("");
    setProblem(null);
    try {
      await sendSms(phone, body);
      setAwaitingReply(true);
      pollUntilRef.current = Date.now() + REPLY_WINDOW_MS;
      setPolling(true);
      await refresh();
    } catch (error) {
      setDraft(body);
      setProblem(`Wiadomość nie została wysłana. ${describeError(error)}`);
    } finally {
      setPending(null);
      draftRef.current?.focus();
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    void send();
  }

  if (status === "demo_off") {
    return (
      <p role="alert" className="rounded-lg border border-line-strong bg-surface p-4">
        <span className="block font-semibold">Symulator jest wyłączony</span>
        Serwer nie działa w trybie demonstracyjnym, więc nie udostępnia podglądu
        rozmowy. Włącz tryb demonstracyjny po stronie serwera i odśwież stronę.
      </p>
    );
  }

  const replyOverdue = awaitingReply && !polling && !sending;

  return (
    <div className="mx-auto w-full max-w-sm overflow-hidden rounded-[1.75rem] border-2 border-line-strong bg-surface">
      <div className="flex items-center justify-between gap-2 border-b border-line bg-subtle px-4 py-2">
        <p className="min-w-0">
          <span className="block font-semibold">Prawdowid</span>
          <span className="block truncate text-sm text-muted">Rozmowa z numeru {phone}</span>
        </p>
        <Button
          variant="quiet"
          onClick={() => void refresh()}
          aria-label="Odśwież rozmowę"
          className="min-w-11 shrink-0 px-2"
        >
          <RefreshCw aria-hidden="true" className="size-5" />
        </Button>
      </div>

      <div
        ref={logRef}
        role="log"
        aria-label="Rozmowa"
        aria-busy={sending || awaitingReply}
        tabIndex={0}
        className="h-[26rem] overflow-y-auto px-3 py-4"
      >
        {status === "loading" ? (
          <p className="flex items-center gap-2 text-muted">
            <Spinner className="size-5" />
            Wczytuję rozmowę…
          </p>
        ) : null}
        {status === "ready" && messages.length === 0 && !sending ? (
          <p className="text-center text-muted">
            Brak wiadomości. Napisz poniżej to, co chcesz sprawdzić.
          </p>
        ) : null}
        <ol className="space-y-3">
          {messages.map((message) => (
            <SmsBubble key={message.id} message={message} />
          ))}
          {pending ? (
            <BubbleFrame direction="in" footer="Wysyłam…">
              {pending}
            </BubbleFrame>
          ) : null}
          {(sending || awaitingReply) && !replyOverdue ? (
            <BubbleFrame direction="out">
              <span className="flex items-center gap-2">
                <Spinner className="size-4" />
                Sprawdzam w źródłach…
              </span>
            </BubbleFrame>
          ) : null}
        </ol>
      </div>

      {problem || replyOverdue ? (
        <p role="alert" className="border-t border-line bg-subtle px-4 py-2">
          {problem ??
            "Odpowiedź jeszcze nie przyszła. Użyj przycisku odświeżania u góry rozmowy."}
        </p>
      ) : null}

      <form
        className="flex items-end gap-2 border-t border-line p-3"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <label htmlFor="sms-tresc" className="sr-only">
          Treść wiadomości
        </label>
        <textarea
          id="sms-tresc"
          ref={draftRef}
          value={draft}
          rows={2}
          placeholder="Napisz wiadomość"
          aria-describedby="sms-pomoc"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          className="min-h-11 min-w-0 flex-1 resize-none rounded-xl border border-line-strong bg-surface px-3 py-2 placeholder:text-muted"
        />
        <Button
          type="submit"
          variant="primary"
          disabled={sending || !draft.trim()}
          aria-label="Wyślij wiadomość"
          className="shrink-0 px-3"
        >
          <Send aria-hidden="true" className="size-5" />
        </Button>
      </form>
    </div>
  );
}

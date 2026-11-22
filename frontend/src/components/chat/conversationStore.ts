import { useSyncExternalStore } from "react";
import { getCheck } from "@/lib/api";
import { cachedResult } from "@/lib/resultCache";
import type { TurnState } from "./ChatAnswer";

export type TurnKind = "image" | "audio" | null;

export interface Turn {
  id: number;
  /** What the user typed, shown in the thread. */
  text: string;
  /** What was sent: `text` with personal data masked in the browser. */
  sentText: string;
  maskedPii: string[];
  file: File | null;
  kind: TurnKind;
  /** Own object URL, so clearing the composer does not break the image in the thread. */
  imageUrl: string | null;
  /** The message was an image; after a reload only this flag is left, not the picture. */
  image: boolean;
  /** Backend check behind this turn, once it has one. */
  resultId: string | null;
  /** The check whose clarifying question this turn answers. */
  parentResultId: string | null;
  state: TurnState;
  /** How long the user waited for the answer (request to response), measured in the browser. */
  elapsedMs?: number;
}

/**
 * The live conversation sits outside the component, so it survives opening a full result:
 * in-flight checks keep running and land here even while the chat is not on screen.
 *
 * Each conversation is also saved in the browser (message text and check ids only; results stay
 * on the backend), so "Wróć do czatu" on a result page can reopen the conversation it came from,
 * even after a reload or when the result was opened from the session list.
 */
interface StoredTurn {
  /** Masked text only: the raw message never reaches browser storage. */
  text: string;
  image: boolean;
  kind?: TurnKind;
  resultId: string;
  parentResultId?: string;
}

interface StoredConversation {
  id: string;
  updatedAt: number;
  turns: StoredTurn[];
}

const STORAGE_KEY = "prawdowid_conversations";
const MAX_CONVERSATIONS = 10;
const MAX_STORED_TEXT = 4000;
const EMPTY: Turn[] = [];

let conversationId = newConversationId();
let turns: Turn[] = EMPTY;
let nextId = 1;
let scrollY = 0;
const requests = new Set<AbortController>();
const listeners = new Set<() => void>();

function newConversationId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function emit(): void {
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function isStoredConversation(value: unknown): value is StoredConversation {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    typeof item.id === "string" &&
    typeof item.updatedAt === "number" &&
    Array.isArray(item.turns) &&
    item.turns.every(
      (turn) =>
        turn &&
        typeof turn === "object" &&
        typeof (turn as StoredTurn).text === "string" &&
        typeof (turn as StoredTurn).resultId === "string",
    )
  );
}

function readStored(): StoredConversation[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed.filter(isStoredConversation) : [];
  } catch {
    return [];
  }
}

function writeStored(conversations: StoredConversation[]): void {
  try {
    if (conversations.length === 0) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch {
    // Without storage a conversation simply cannot be reopened after a reload.
  }
}

/** Saves the turns that have a check behind them; failures without one are not worth reopening. */
function persist(): void {
  const stored: StoredTurn[] = turns.flatMap((turn) =>
    turn.resultId
      ? [
          {
            text: turn.sentText.slice(0, MAX_STORED_TEXT),
            image: turn.image,
            ...(turn.kind ? { kind: turn.kind } : {}),
            resultId: turn.resultId,
            ...(turn.parentResultId ? { parentResultId: turn.parentResultId } : {}),
          },
        ]
      : [],
  );
  const others = readStored().filter((item) => item.id !== conversationId);
  const current = stored.length > 0 ? [{ id: conversationId, updatedAt: Date.now(), turns: stored }] : [];
  writeStored([...current, ...others].slice(0, MAX_CONVERSATIONS));
}

export function useTurns(): Turn[] {
  return useSyncExternalStore(
    subscribe,
    () => turns,
    () => EMPTY,
  );
}

export interface NewTurn {
  text: string;
  sentText: string;
  maskedPii: string[];
  file: File | null;
  kind: TurnKind;
  parentResultId: string | null;
}

export function addTurn(turn: NewTurn): number {
  const id = nextId++;
  const imageUrl = turn.file && turn.kind === "image" ? URL.createObjectURL(turn.file) : null;
  turns = [
    ...turns,
    { ...turn, id, imageUrl, image: turn.kind === "image", resultId: null, state: { kind: "loading" } },
  ];
  emit();
  return id;
}

export function updateTurn(id: number, state: TurnState, elapsedMs?: number): void {
  const resultId = state.kind === "result" ? state.result.id : undefined;
  turns = turns.map((turn) =>
    turn.id === id
      ? { ...turn, state, resultId: resultId ?? turn.resultId, elapsedMs: elapsedMs ?? turn.elapsedMs }
      : turn,
  );
  emit();
  if (resultId) persist();
}

/** Registers a request so "Nowa sesja" can cancel it; call the returned function when it ends. */
export function trackRequest(controller: AbortController): () => void {
  requests.add(controller);
  return () => requests.delete(controller);
}

export function saveScroll(y: number): void {
  scrollY = y;
}

export function savedScroll(): number {
  return scrollY;
}

function clearLive(): void {
  requests.forEach((controller) => controller.abort());
  requests.clear();
  turns.forEach((turn) => {
    if (turn.imageUrl) URL.revokeObjectURL(turn.imageUrl);
  });
  turns = EMPTY;
  scrollY = 0;
}

export function resetConversation(): void {
  clearLive();
  conversationId = newConversationId();
  emit();
}

/** The conversation that asked for this check, if this browser has it. */
function conversationOf(checkId: string): string | null {
  if (turns.some((turn) => turn.resultId === checkId)) return conversationId;
  return readStored().find((item) => item.turns.some((turn) => turn.resultId === checkId))?.id ?? null;
}

/** `null` on the server and when the conversation is not saved in this browser. */
export function useConversationOf(checkId: string): string | null {
  return useSyncExternalStore(
    subscribe,
    () => conversationOf(checkId),
    () => null,
  );
}

/**
 * Makes a saved conversation the live one and reloads its results from the backend.
 * Returns false when it is not saved here (e.g. cleared storage); the chat then stays as it is.
 */
export function openConversation(id: string): boolean {
  if (id === conversationId && turns.length > 0) return true;
  const stored = readStored().find((item) => item.id === id);
  if (!stored) return false;

  clearLive();
  conversationId = id;
  turns = stored.turns.map((turn) => ({
    id: nextId++,
    text: turn.text,
    sentText: turn.text,
    maskedPii: [],
    file: null,
    kind: turn.kind ?? (turn.image ? "image" : null),
    imageUrl: null,
    image: turn.image,
    resultId: turn.resultId,
    parentResultId: turn.parentResultId ?? null,
    state: { kind: "loading" },
  }));
  emit();

  for (const turn of turns) loadResult(turn.id, turn.resultId!);
  return true;
}

/** Fetches a saved turn's result again, e.g. after it failed to load. */
export function reloadResult(turnId: number): void {
  const turn = turns.find((item) => item.id === turnId);
  if (!turn?.resultId) return;
  updateTurn(turnId, { kind: "loading" });
  loadResult(turnId, turn.resultId);
}

function loadResult(turnId: number, resultId: string): void {
  const cached = cachedResult(resultId);
  if (cached) {
    updateTurn(turnId, { kind: "result", result: cached });
    return;
  }
  const controller = new AbortController();
  const untrack = trackRequest(controller);
  getCheck(resultId, controller.signal)
    .then((result) => updateTurn(turnId, { kind: "result", result }))
    .catch((error: unknown) => {
      if (!controller.signal.aborted) updateTurn(turnId, { kind: "failure", error });
    })
    .finally(untrack);
}

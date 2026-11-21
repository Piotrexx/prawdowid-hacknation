import { useSyncExternalStore } from "react";
import type { CheckResponse, Verdict } from "./types";

/** Completed checks made in this browser, newest first. Only the backend holds the full result. */
export interface HistoryEntry {
  id: string;
  preview: string;
  verdicts: Verdict[];
  /** Missing in entries saved before this field existed. */
  claims?: number;
  createdAt: string;
}

const STORAGE_KEY = "prawdowid_history";
const MAX_ENTRIES = 10;
const PREVIEW_LENGTH = 90;
const EMPTY: HistoryEntry[] = [];

const listeners = new Set<() => void>();
let cache: { raw: string | null; entries: HistoryEntry[] } | null = null;

function isEntry(value: unknown): value is HistoryEntry {
  if (!value || typeof value !== "object") return false;
  const entry = value as Record<string, unknown>;
  return (
    typeof entry.id === "string" &&
    typeof entry.preview === "string" &&
    typeof entry.createdAt === "string" &&
    Array.isArray(entry.verdicts)
  );
}

function readRaw(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function getSnapshot(): HistoryEntry[] {
  const raw = readRaw();
  if (cache && cache.raw === raw) return cache.entries;
  let entries = EMPTY;
  try {
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (Array.isArray(parsed)) entries = parsed.filter(isEntry);
  } catch {
    entries = EMPTY;
  }
  cache = { raw, entries };
  return entries;
}

function write(entries: HistoryEntry[]): void {
  try {
    if (entries.length === 0) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Without storage the list simply stays empty.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) listener();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

function previewOf(result: CheckResponse): string {
  const source =
    result.input.title?.trim() ||
    result.claims[0]?.text.trim() ||
    result.input.text.trim() ||
    result.input.url?.trim() ||
    "Sprawdzenie bez treści";
  const flat = source.replace(/\s+/g, " ");
  return flat.length > PREVIEW_LENGTH ? `${flat.slice(0, PREVIEW_LENGTH - 1)}…` : flat;
}

export function rememberCheck(result: CheckResponse): void {
  const entry: HistoryEntry = {
    id: result.id,
    preview: previewOf(result),
    verdicts: Array.from(new Set(result.claims.map((claim) => claim.verdict))),
    claims: result.claims.length,
    createdAt: result.created_at,
  };
  const rest = getSnapshot().filter((item) => item.id !== entry.id);
  write([entry, ...rest].slice(0, MAX_ENTRIES));
}

export function clearHistory(): void {
  write([]);
}

/** `null` until the browser's storage has been read, so the server never renders an empty list. */
export function useHistory(): HistoryEntry[] | null {
  return useSyncExternalStore<HistoryEntry[] | null>(subscribe, getSnapshot, () => null);
}

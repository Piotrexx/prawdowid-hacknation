import { useSyncExternalStore } from "react";

const STORAGE_KEY = "prawdowid_admin_token";
const listeners = new Set<() => void>();

// Keeps the panel usable for the current page view when sessionStorage is blocked.
let memoryToken: string | null = null;

function readToken(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

export function writeAdminToken(token: string | null): void {
  memoryToken = token;
  try {
    if (token === null) window.sessionStorage.removeItem(STORAGE_KEY);
    else window.sessionStorage.setItem(STORAGE_KEY, token);
  } catch {
    // The in-memory copy above is the fallback.
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Null on the server and until a token is saved, so the first render always shows the prompt. */
export function useAdminToken(): string | null {
  return useSyncExternalStore(subscribe, readToken, () => null);
}

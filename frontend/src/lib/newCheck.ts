import { useSyncExternalStore } from "react";

/**
 * "Nowa sesja" lives in the app sidebar, the conversation on the home page. The sidebar bumps
 * this counter; the conversation is keyed by it, so a new value starts it afresh.
 */
let count = 0;
const listeners = new Set<() => void>();

export function requestNewCheck(): void {
  count += 1;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useNewCheckCount(): number {
  return useSyncExternalStore(
    subscribe,
    () => count,
    () => 0,
  );
}

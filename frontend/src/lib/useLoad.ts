import { useCallback, useEffect, useEffectEvent, useState } from "react";
import { isAbort } from "./api";

export type Loadable<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: unknown };

interface Settled<T> {
  requestKey: string;
  state: Loadable<T>;
}

const LOADING = { status: "loading" } as const;

/**
 * Fetches on mount and whenever `key` changes. A result that belongs to an older key
 * is ignored, so the state shown always matches the current request.
 */
export function useLoad<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const requestKey = `${key}#${attempt}`;
  const runLoad = useEffectEvent(load);

  useEffect(() => {
    const controller = new AbortController();
    runLoad(controller.signal).then(
      (data) => setSettled({ requestKey, state: { status: "ready", data } }),
      (error: unknown) => {
        if (isAbort(error)) return;
        setSettled({ requestKey, state: { status: "error", error } });
      },
    );
    return () => controller.abort();
  }, [requestKey]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  const mutate = useCallback((update: (data: T) => T) => {
    setSettled((current) =>
      current?.state.status === "ready"
        ? { ...current, state: { status: "ready", data: update(current.state.data) } }
        : current,
    );
  }, []);

  const state: Loadable<T> = settled?.requestKey === requestKey ? settled.state : LOADING;
  return { state, reload, mutate };
}

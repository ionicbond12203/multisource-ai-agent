"use client";

import { useCallback, useEffect, useState } from "react";

interface Settled<T> {
  key: string;
  data?: T;
  error?: string;
}

export interface Remote<T> {
  /** The latest data received. While a new request runs, the previous data stays here so the UI doesn't flash. */
  data: T | undefined;
  /** Error of the current request, if it failed. */
  error: string | undefined;
  /** True while the current request (for the current `key`) hasn't settled. */
  loading: boolean;
  retry: () => void;
}

/**
 * Loads `load()` whenever `key` changes, cancelling the previous request.
 * Pass `key = null` to load nothing.
 */
export function useRemote<T>(key: string | null, load: (signal: AbortSignal) => Promise<T>): Remote<T> {
  const [attempt, setAttempt] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const [latest, setLatest] = useState<T | undefined>(undefined);
  const requestKey = key === null ? null : `${key}#${attempt}`;

  useEffect(() => {
    if (requestKey === null) return;
    const controller = new AbortController();
    load(controller.signal)
      .then((data) => {
        setSettled({ key: requestKey, data });
        setLatest(data);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setSettled({
          key: requestKey,
          error: error instanceof Error ? error.message : "Something went wrong.",
        });
      });
    return () => controller.abort();
    // `load` is recreated on every render; `requestKey` already captures everything it depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey]);

  const current = settled?.key === requestKey ? settled : undefined;
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return {
    data: latest,
    error: current?.error,
    loading: requestKey !== null && current === undefined,
    retry,
  };
}

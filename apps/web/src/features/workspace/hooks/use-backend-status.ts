"use client";

import { useEffect, useState } from "react";

/**
 * - checking: the first health check is still under way (usually well under a second)
 * - ready: the backend answered
 * - waking: no answer yet; the free host is starting the server after a sleep
 * - unreachable: still no answer after `giveUpAfterMs`
 */
export type BackendStatus = "checking" | "ready" | "waking" | "unreachable";

export interface BackendStatusOptions {
  /** How long the first check may take before we tell the user the server is waking up. */
  firstCheckTimeoutMs?: number;
  retryEveryMs?: number;
  giveUpAfterMs?: number;
}

/**
 * Polls GET {baseUrl}/health so the page can explain a cold start.
 * The free Render instance sleeps after 15 idle minutes, and the first request
 * then takes up to a minute; without a notice the app just looks broken.
 * Without a backend (`baseUrl` undefined) there is nothing to wait for.
 */
export function useBackendStatus(
  baseUrl: string | undefined,
  { firstCheckTimeoutMs = 4000, retryEveryMs = 3000, giveUpAfterMs = 120_000 }: BackendStatusOptions = {},
): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>(baseUrl ? "checking" : "ready");

  useEffect(() => {
    if (!baseUrl) return;
    let cancelled = false;
    const controller = new AbortController();
    const startedAt = Date.now();

    async function poll() {
      let attempt = 0;
      while (!cancelled) {
        const timeout = attempt === 0 ? firstCheckTimeoutMs : Math.max(retryEveryMs * 3, 10_000);
        if (await isHealthy(`${baseUrl}/health`, timeout, controller.signal)) {
          if (!cancelled) setStatus("ready");
          return;
        }
        if (cancelled) return;
        if (Date.now() - startedAt >= giveUpAfterMs) {
          setStatus("unreachable");
          return;
        }
        setStatus("waking");
        attempt += 1;
        await sleep(retryEveryMs, controller.signal);
      }
    }

    void poll();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [baseUrl, firstCheckTimeoutMs, retryEveryMs, giveUpAfterMs]);

  return status;
}

async function isHealthy(url: string, timeoutMs: number, signal: AbortSignal): Promise<boolean> {
  const attempt = new AbortController();
  const timer = setTimeout(() => attempt.abort(), timeoutMs);
  const stop = () => attempt.abort();
  signal.addEventListener("abort", stop);
  try {
    const response = await fetch(url, { signal: attempt.signal, cache: "no-store" });
    return response.ok;
  } catch {
    return false; // timed out, network error, or the host is still starting
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", stop);
  }
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

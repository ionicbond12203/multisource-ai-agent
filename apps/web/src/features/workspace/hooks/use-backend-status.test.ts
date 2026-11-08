import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useBackendStatus } from "./use-backend-status";

const FAST = { firstCheckTimeoutMs: 50, retryEveryMs: 10, giveUpAfterMs: 200 };

function mockFetch(responses: Array<"ok" | "fail" | "hang">) {
  let call = 0;
  const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
    const next = responses[Math.min(call++, responses.length - 1)];
    if (next === "ok") return Promise.resolve(new Response("{}", { status: 200 }));
    if (next === "fail") return Promise.reject(new TypeError("Failed to fetch"));
    // "hang": never answers until aborted, like a server that is still starting
    return new Promise<Response>((_resolve, reject) =>
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useBackendStatus", () => {
  it("is ready at once without a backend", () => {
    const { result } = renderHook(() => useBackendStatus(undefined, FAST));
    expect(result.current).toBe("ready");
  });

  it("becomes ready when the health check answers", async () => {
    const fetchMock = mockFetch(["ok"]);
    const { result } = renderHook(() => useBackendStatus("https://api.test", FAST));
    expect(result.current).toBe("checking");
    await waitFor(() => expect(result.current).toBe("ready"));
    expect(fetchMock).toHaveBeenCalledWith("https://api.test/health", expect.anything());
  });

  it("shows waking while a sleeping server starts, then ready", async () => {
    let serverUp = false;
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        serverUp
          ? Promise.resolve(new Response("{}", { status: 200 }))
          : Promise.reject(new TypeError("Failed to fetch")),
      ),
    );
    const { result } = renderHook(() =>
      useBackendStatus("https://api.test", { ...FAST, giveUpAfterMs: 5000 }),
    );

    await waitFor(() => expect(result.current).toBe("waking"));
    serverUp = true;
    await waitFor(() => expect(result.current).toBe("ready"));
  });

  it("treats a first check that takes too long as waking", async () => {
    mockFetch(["hang"]);
    const { result } = renderHook(() =>
      useBackendStatus("https://api.test", { ...FAST, giveUpAfterMs: 5000 }),
    );
    await waitFor(() => expect(result.current).toBe("waking"));
  });

  it("gives up after the time limit", async () => {
    mockFetch(["fail"]);
    const { result } = renderHook(() => useBackendStatus("https://api.test", FAST));
    await waitFor(() => expect(result.current).toBe("unreachable"), { timeout: 2000 });
  });
});

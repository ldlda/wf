import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  PRESENTATION_SYNC_GRANT_STORAGE_KEY,
  type PresentationSyncClientDependencies,
} from "./presentation-sync-client.js";
import { usePresentationSync } from "./usePresentationSync.js";

const grant = {
  sessionId: "session-1",
  code: "ABC123",
  connectionToken: "token-1",
  websocketPath: "/api/presentation-sync/ws" as const,
  snapshot: { hash: "#scene/thesis/title", revision: 0 },
};

class MemoryStorage implements Storage {
  private readonly values = new Map<string, string>();

  get length(): number {
    return this.values.size;
  }

  clear(): void {
    this.values.clear();
  }

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  key(index: number): string | null {
    return [...this.values.keys()][index] ?? null;
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

class FakeSocket {
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  readonly sent: string[] = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: { readonly data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((event: { readonly code: number; readonly reason: string }) => void) | null = null;

  constructor(readonly url: string) {}

  send(message: string): void {
    this.sent.push(message);
  }

  open(): void {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }

  serverMessage(message: unknown): void {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  close(code = 1000, reason = "closed"): void {
    this.readyState = FakeSocket.CLOSED;
    this.onclose?.({ code, reason });
  }
}

const snapshot = (hash: string, revision: number) => ({
  type: "location.snapshot",
  snapshot: { hash, revision },
  originatingMessageId: null,
});

const presence = (presenters: number, audience: number) => ({
  type: "presence.snapshot",
  presence: { presenters, audience },
});

const makeDependencies = () => {
  const storage = new MemoryStorage();
  const sockets: FakeSocket[] = [];
  const fetch = vi.fn<typeof globalThis.fetch>();
  const dependencies: PresentationSyncClientDependencies & {
    readonly location: { readonly search: string; readonly href: string };
    readonly history: { readonly replaceState: ReturnType<typeof vi.fn> };
  } = {
    fetch,
    createWebSocket: (url: string) => {
      const socket = new FakeSocket(url);
      sockets.push(socket);
      return socket as unknown as WebSocket;
    },
    storage,
    origin: "http://console.test",
    protocol: "http:",
    setTimeout: globalThis.setTimeout,
    clearTimeout: globalThis.clearTimeout,
    location: { search: "", href: "http://console.test/present" },
    history: { replaceState: vi.fn() },
  };
  return { dependencies, sockets, storage, fetch };
};

const resolvedGrant = () =>
  new Response(JSON.stringify(grant), { status: 201 });

const connectSession = async (
  result: { readonly current: ReturnType<typeof usePresentationSync> },
  sockets: FakeSocket[],
  hash = "#scene/thesis/title",
): Promise<void> => {
  await act(async () => {
    await result.current.startSession();
  });
  await act(async () => {
    sockets[0]?.open();
    sockets[0]?.serverMessage(snapshot(hash, hash === "#scene/thesis/title" ? 0 : 1));
    sockets[0]?.serverMessage(presence(1, 1));
  });
};

describe("usePresentationSync", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("publishes one local hash change after the server snapshot is ready", async () => {
    const { dependencies, sockets, fetch } = makeDependencies();
    fetch.mockImplementation(async () => resolvedGrant());
    const applyRemoteHash = vi.fn();
    const { result, rerender } = renderHook(
      ({ hash }) =>
        usePresentationSync({
          role: "presenter",
          currentHash: hash,
          applyRemoteHash,
          dependencies,
        }),
      { initialProps: { hash: "#scene/thesis/title" } },
    );

    await connectSession(result, sockets);
    expect(sockets[0]?.sent).toHaveLength(0);

    rerender({ hash: "#scene/problem/direct-actions" });

    expect(sockets[0]?.sent).toHaveLength(1);
    expect(JSON.parse(sockets[0]?.sent[0] ?? "{}")).toMatchObject({
      type: "location.publish",
      hash: "#scene/problem/direct-actions",
      baseRevision: 0,
    });
  });

  it("applies a remote hash without publishing it back", async () => {
    const { dependencies, sockets, fetch } = makeDependencies();
    fetch.mockImplementation(async () => resolvedGrant());
    const applyRemoteHash = vi.fn();
    const { result, rerender } = renderHook(
      ({ hash }) =>
        usePresentationSync({
          role: "audience",
          currentHash: hash,
          applyRemoteHash,
          dependencies,
        }),
      { initialProps: { hash: "#scene/thesis/title" } },
    );

    await connectSession(result, sockets);
    await act(async () => {
      sockets[0]?.serverMessage(snapshot("#scene/problem/direct-actions", 1));
    });
    expect(applyRemoteHash).toHaveBeenCalledWith("#scene/problem/direct-actions");

    rerender({ hash: "#scene/problem/direct-actions" });

    expect(sockets[0]?.sent.filter((message) =>
      JSON.parse(message).type === "location.publish",
    )).toHaveLength(0);
  });

  it("applies stale rejection snapshots and does not echo convergence", async () => {
    const { dependencies, sockets, fetch } = makeDependencies();
    fetch.mockImplementation(async () => resolvedGrant());
    const applyRemoteHash = vi.fn();
    const { result, rerender } = renderHook(
      ({ hash }) =>
        usePresentationSync({
          role: "audience",
          currentHash: hash,
          applyRemoteHash,
          dependencies,
        }),
      { initialProps: { hash: "#scene/thesis/title" } },
    );

    await connectSession(result, sockets);
    await act(async () => {
      sockets[0]?.serverMessage({
        type: "location.rejected",
        reason: "stale_revision",
        current: {
          hash: "#scene/problem/direct-actions",
          revision: 4,
        },
        messageId: "1-stale",
      });
    });
    rerender({ hash: "#scene/problem/direct-actions" });

    expect(applyRemoteHash).toHaveBeenCalledWith("#scene/problem/direct-actions");
    expect(sockets[0]?.sent.filter((message) =>
      JSON.parse(message).type === "location.publish",
    )).toHaveLength(0);
  });

  it("lets the server snapshot win after reconnecting over local navigation", async () => {
    vi.useFakeTimers();
    const { dependencies, sockets, fetch } = makeDependencies();
    fetch.mockImplementation(async () => resolvedGrant());
    const applyRemoteHash = vi.fn();
    const { result, rerender } = renderHook(
      ({ hash }) =>
        usePresentationSync({
          role: "presenter",
          currentHash: hash,
          applyRemoteHash,
          dependencies,
        }),
      { initialProps: { hash: "#scene/thesis/title" } },
    );

    await connectSession(result, sockets);
    sockets[0]?.close(1006, "network");
    rerender({ hash: "#scene/problem/direct-actions" });
    expect(sockets[0]?.sent).toHaveLength(0);

    await act(async () => {
      vi.advanceTimersByTime(500);
    });
    await act(async () => {
      sockets[1]?.open();
      sockets[1]?.serverMessage(snapshot("#scene/architecture/runtime", 2));
      sockets[1]?.serverMessage(presence(1, 1));
    });
    rerender({ hash: "#scene/architecture/runtime" });

    expect(applyRemoteHash).toHaveBeenCalledWith("#scene/architecture/runtime");
    expect(sockets[1]?.sent.filter((message) =>
      JSON.parse(message).type === "location.publish",
    )).toHaveLength(0);
  });

  it("keeps local navigation standalone when session creation fails", async () => {
    const { dependencies, fetch } = makeDependencies();
    fetch.mockRejectedValue(new Error("server unavailable"));
    const applyRemoteHash = vi.fn();
    const { result, rerender } = renderHook(
      ({ hash }) =>
        usePresentationSync({
          role: "presenter",
          currentHash: hash,
          applyRemoteHash,
          dependencies,
        }),
      { initialProps: { hash: "#scene/thesis/title" } },
    );

    await act(async () => {
      await result.current.startSession();
    });
    rerender({ hash: "#scene/problem/direct-actions" });

    expect(result.current.state).toEqual({
      kind: "failed",
      message: "server unavailable",
      retryable: true,
    });
    expect(applyRemoteHash).not.toHaveBeenCalled();
  });

  it("consumes a query-string pair code once on mount", async () => {
    const { dependencies, sockets, fetch } = makeDependencies();
    const pairDependencies = {
      ...dependencies,
      location: {
        search: "?pair=ab-c%20123",
        href: "http://console.test/present?pair=ab-c%20123",
      },
    };
    fetch.mockImplementation(async () => resolvedGrant());
    const { result, rerender } = renderHook(
      ({ hash }) =>
        usePresentationSync({
          role: "audience",
          currentHash: hash,
          applyRemoteHash: () => {},
          dependencies: pairDependencies,
        }),
      { initialProps: { hash: "#scene/thesis/title" } },
    );

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenCalledWith(
      "http://console.test/api/presentation-sync/sessions/join",
      expect.objectContaining({
        body: JSON.stringify({ role: "audience", code: "ABC123" }),
      }),
    );
    rerender({ hash: "#scene/thesis/title" });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(sockets).toHaveLength(1);
    expect(result.current.state.kind).toBe("waiting");
  });

  it("closes the socket and reconnect timer on unmount", async () => {
    vi.useFakeTimers();
    const { dependencies, sockets, fetch, storage } = makeDependencies();
    fetch.mockImplementation(async () => resolvedGrant());
    const { result, unmount } = renderHook(() =>
      usePresentationSync({
        role: "presenter",
        currentHash: "#scene/thesis/title",
        applyRemoteHash: () => {},
        dependencies,
      }),
    );

    await connectSession(result, sockets);
    unmount();
    vi.advanceTimersByTime(10_000);

    expect(sockets).toHaveLength(1);
    expect(sockets[0]?.readyState).toBe(FakeSocket.CLOSED);
    expect(storage.getItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY)).not.toBeNull();
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createPresentationSyncClient,
  PRESENTATION_SYNC_GRANT_STORAGE_KEY,
  presentationSyncJoinUrl,
  type PresentationSyncClientEvent,
} from "./presentation-sync-client.js";

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
  readonly closeCalls: Array<readonly [number | undefined, string | undefined]> = [];
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

  close(code?: number, reason?: string): void {
    this.closeCalls.push([code, reason]);
    this.readyState = FakeSocket.CLOSED;
    this.onclose?.({ code: code ?? 1000, reason: reason ?? "closed" });
  }
}

const makeDependencies = (storage: Storage, sockets: FakeSocket[]) => ({
  fetch: vi.fn<typeof fetch>(),
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
});

describe("presentation sync client", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("posts create and join to same-origin HTTP paths and normalizes codes", async () => {
    const storage = new MemoryStorage();
    const sockets: FakeSocket[] = [];
    const dependencies = makeDependencies(storage, sockets);
    dependencies.fetch.mockImplementation(async () =>
      new Response(JSON.stringify(grant), { status: 201 }),
    );
    const client = createPresentationSyncClient(dependencies);

    await client.create("presenter", "#scene/thesis/title");
    expect(dependencies.fetch).toHaveBeenNthCalledWith(
      1,
      "http://console.test/api/presentation-sync/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          role: "presenter",
          initialHash: "#scene/thesis/title",
        }),
      }),
    );

    await client.join("audience", "ab-c 123");
    expect(dependencies.fetch).toHaveBeenNthCalledWith(
      2,
      "http://console.test/api/presentation-sync/sessions/join",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ role: "audience", code: "ABC123" }),
      }),
    );
    expect(storage.getItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY)).toBeNull();

    client.connect(grant, () => {});
    expect(storage.getItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY)).toContain(
      '"connectionToken":"token-1"',
    );
  });

  it("uses wss for HTTPS and builds the opposite-route join URL", () => {
    const storage = new MemoryStorage();
    const sockets: FakeSocket[] = [];
    const dependencies = makeDependencies(storage, sockets);
    const client = createPresentationSyncClient({
      ...dependencies,
      origin: "https://console.test",
      protocol: "https:",
    });
    const events: PresentationSyncClientEvent[] = [];

    client.connect(grant, (event) => events.push(event));
    expect(sockets[0]?.url).toBe(
      "wss://console.test/api/presentation-sync/ws?token=token-1",
    );
    expect(presentationSyncJoinUrl("presenter", "ab-c 123", "https://console.test")).toBe(
      "https://console.test/present?pair=ABC123",
    );
    expect(presentationSyncJoinUrl("audience", "ABC123", "https://console.test")).toBe(
      "https://console.test/presenter?pair=ABC123",
    );
    expect(events).toEqual([]);
  });

  it("restores a saved grant after reload", () => {
    const storage = new MemoryStorage();
    storage.setItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY, JSON.stringify(grant));
    const sockets: FakeSocket[] = [];
    const client = createPresentationSyncClient(makeDependencies(storage, sockets));

    expect(client.restoreGrant()).toEqual(grant);
  });

  it("uses bounded reconnect delays of 500, 1000, 2000, then 5000 milliseconds", () => {
    vi.useFakeTimers();
    const storage = new MemoryStorage();
    const sockets: FakeSocket[] = [];
    const client = createPresentationSyncClient(makeDependencies(storage, sockets));
    const events: PresentationSyncClientEvent[] = [];

    client.connect(grant, (event) => events.push(event));
    sockets[0]?.close(1006, "network");
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(499);
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(2);

    sockets[1]?.close(1006, "network");
    vi.advanceTimersByTime(999);
    expect(sockets).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(3);

    sockets[2]?.close(1006, "network");
    vi.advanceTimersByTime(1_999);
    expect(sockets).toHaveLength(3);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(4);

    sockets[3]?.close(1006, "network");
    vi.advanceTimersByTime(4_999);
    expect(sockets).toHaveLength(4);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(5);

    expect(events.filter((event) => event.type === "reconnecting")).toHaveLength(4);
  });

  it("clears the grant and never reconnects after a terminal server event", () => {
    vi.useFakeTimers();
    const storage = new MemoryStorage();
    storage.setItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY, JSON.stringify(grant));
    const sockets: FakeSocket[] = [];
    const client = createPresentationSyncClient(makeDependencies(storage, sockets));
    const events: PresentationSyncClientEvent[] = [];

    client.connect(grant, (event) => events.push(event));
    sockets[0]?.serverMessage({ type: "session.ended", reason: "expired" });
    sockets[0]?.close(1000, "expired");
    vi.advanceTimersByTime(10_000);

    expect(storage.getItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY)).toBeNull();
    expect(sockets).toHaveLength(1);
    expect(events).toContainEqual({ type: "ended", reason: "expired" });
  });

  it("clears the grant and never reconnects after explicit leave", () => {
    vi.useFakeTimers();
    const storage = new MemoryStorage();
    storage.setItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY, JSON.stringify(grant));
    const sockets: FakeSocket[] = [];
    const client = createPresentationSyncClient(makeDependencies(storage, sockets));

    client.connect(grant, () => {});
    client.leave();
    vi.advanceTimersByTime(10_000);

    expect(storage.getItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY)).toBeNull();
    expect(sockets).toHaveLength(1);
  });

  it("refuses to end while the socket is reconnecting", () => {
    vi.useFakeTimers();
    const storage = new MemoryStorage();
    const sockets: FakeSocket[] = [];
    const client = createPresentationSyncClient(makeDependencies(storage, sockets));

    client.connect(grant, () => {});
    sockets[0]?.open();
    sockets[0]?.close(1006, "network");

    expect(client.end()).toBe(false);
    expect(storage.getItem(PRESENTATION_SYNC_GRANT_STORAGE_KEY)).not.toBeNull();
    vi.advanceTimersByTime(500);
    expect(sockets).toHaveLength(2);
  });

  it("closes socket errors without using reserved close code 1006", () => {
    const storage = new MemoryStorage();
    const sockets: FakeSocket[] = [];
    const client = createPresentationSyncClient(makeDependencies(storage, sockets));

    client.connect(grant, () => {});
    sockets[0]?.onerror?.();

    expect(sockets[0]?.closeCalls).toEqual([[undefined, undefined]]);
    expect(sockets[0]?.closeCalls.some(([code]) => code === 1006)).toBe(false);
  });
});

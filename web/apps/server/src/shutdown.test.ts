import { EventEmitter, once } from "node:events";
import type { AddressInfo } from "node:net";
import {
  serve,
  upgradeWebSocket,
  type WebSocketServerLike,
} from "@hono/node-server";
import { Hono } from "hono";
import { describe, expect, it, vi } from "vitest";
import WebSocket, { WebSocketServer } from "ws";
import { shutdownServer } from "./shutdown.js";

const closable = () => ({
  close: vi.fn<(code: number, reason: string) => void>(),
  terminate: vi.fn<() => void>(),
});

describe("shutdownServer", () => {
  it("completes cleanly with a real active WebSocket client", async () => {
    const app = new Hono();
    app.get("/ws", upgradeWebSocket(() => ({})));
    const wss = new WebSocketServer({ noServer: true });
    const server = serve({
      fetch: app.fetch,
      websocket: { server: wss as WebSocketServerLike },
      port: 0,
    });
    if (!server.listening) await once(server, "listening");
    const { port } = server.address() as AddressInfo;
    const client = new WebSocket(`ws://127.0.0.1:${port}/ws`);
    await once(client, "open");
    const clientClosed = once(client, "close");
    const exited = new Promise<number>((resolve) => {
      shutdownServer({ server, wss, exit: resolve });
    });

    expect((await clientClosed)[0]).toBe(1001);
    await expect(exited).resolves.toBe(0);
  });

  it("closes active WebSocket clients and exits zero after both servers close", () => {
    const client = closable();
    let closeHttp: (() => void) | undefined;
    let closeWebSockets: (() => void) | undefined;
    const exit = vi.fn<(code: number) => void>();
    const clearForceTimeout = vi.fn<(handle: ReturnType<typeof setTimeout>) => void>();
    const forceHandle = { unref: vi.fn() } as unknown as ReturnType<typeof setTimeout>;
    const setForceTimeout = vi.fn(() => forceHandle);

    shutdownServer({
      server: {
        close: (callback) => {
          closeHttp = callback;
          return new EventEmitter() as never;
        },
        closeAllConnections: vi.fn(),
      },
      wss: {
        clients: new Set([client]),
        close: (callback) => {
          closeWebSockets = callback;
        },
      },
      exit,
      setForceTimeout,
      clearForceTimeout,
    });

    expect(client.close).toHaveBeenCalledWith(1001, "server shutdown");
    closeWebSockets?.();
    expect(exit).not.toHaveBeenCalled();
    closeHttp?.();
    expect(exit).toHaveBeenCalledExactlyOnceWith(0);
    expect(clearForceTimeout).toHaveBeenCalledWith(forceHandle);
    expect(setForceTimeout).toHaveBeenCalledWith(expect.any(Function), 5_000);
    expect(forceHandle.unref).toHaveBeenCalled();
  });

  it("force-terminates lingering clients and chooses exit one only on timeout", () => {
    const client = closable();
    const exit = vi.fn<(code: number) => void>();
    const closeAllConnections = vi.fn();
    let force: (() => void) | undefined;

    shutdownServer({
      server: {
        close: vi.fn(() => new EventEmitter() as never),
        closeAllConnections,
      },
      wss: { clients: new Set([client]), close: vi.fn() },
      exit,
      setForceTimeout: (callback) => {
        force = callback;
        return { unref: vi.fn() } as unknown as ReturnType<typeof setTimeout>;
      },
      clearForceTimeout: vi.fn(),
    });

    expect(exit).not.toHaveBeenCalled();
    force?.();
    expect(client.terminate).toHaveBeenCalledOnce();
    expect(closeAllConnections).toHaveBeenCalledOnce();
    expect(exit).toHaveBeenCalledExactlyOnceWith(1);
  });
});

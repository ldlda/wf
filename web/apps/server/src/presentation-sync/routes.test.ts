import { once } from "node:events";
import type { AddressInfo } from "node:net";
import {
  serve,
  upgradeWebSocket,
  type WebSocketServerLike,
} from "@hono/node-server";
import {
  MAX_SYNC_MESSAGE_BYTES,
  type ServerSyncMessage,
  type SessionGrant,
} from "@lda/presentation-sync";
import { Hono } from "hono";
import { afterEach, describe, expect, it } from "vitest";
import WebSocket, { WebSocketServer } from "ws";
import { addPresentationSyncRoutes } from "./routes.js";
import { createPresentationRoomService } from "./rooms.js";

type RunningServer = {
  readonly origin: string;
  readonly stop: () => Promise<void>;
};

const sockets = new Set<WebSocket>();
const servers = new Set<RunningServer>();

afterEach(async () => {
  for (const socket of sockets) socket.terminate();
  sockets.clear();
  await Promise.all([...servers].map((server) => server.stop()));
  servers.clear();
});

const startServer = async (): Promise<RunningServer> => {
  const app = new Hono();
  addPresentationSyncRoutes(app, {
    rooms: createPresentationRoomService(),
    upgradeWebSocket,
  });
  const wss = new WebSocketServer({ noServer: true });
  const server = serve({
    fetch: app.fetch,
    // @types/ws makes noServer optional even though this instance fixes it to true.
    websocket: { server: wss as WebSocketServerLike },
    port: 0,
  });
  if (!server.listening) await once(server, "listening");
  const { port } = server.address() as AddressInfo;
  const running: RunningServer = {
    origin: `http://127.0.0.1:${port}`,
    stop: async () => {
      wss.close();
      await new Promise<void>((resolve, reject) =>
        server.close((error) => (error ? reject(error) : resolve())),
      );
    },
  };
  servers.add(running);
  return running;
};

const postJson = async (
  origin: string,
  path: string,
  body: unknown,
): Promise<Response> =>
  fetch(`${origin}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

const grant = async (
  origin: string,
  path: string,
  body: unknown,
): Promise<SessionGrant> => {
  const response = await postJson(origin, path, body);
  expect(response.status).toBe(path.endsWith("/join") ? 200 : 201);
  return (await response.json()) as SessionGrant;
};

const messageQueues = new WeakMap<WebSocket, ServerSyncMessage[]>();
const messageWaiters = new WeakMap<WebSocket, Set<() => void>>();

const trackMessages = (socket: WebSocket): void => {
  const queue: ServerSyncMessage[] = [];
  const waiters = new Set<() => void>();
  messageQueues.set(socket, queue);
  messageWaiters.set(socket, waiters);
  socket.on("message", (data) => {
    queue.push(JSON.parse(data.toString()) as ServerSyncMessage);
    for (const wake of waiters) wake();
  });
};

const expectMessage = async (
  socket: WebSocket,
  predicate: (message: ServerSyncMessage) => boolean,
): Promise<ServerSyncMessage> => {
  const queue = messageQueues.get(socket);
  const waiters = messageWaiters.get(socket);
  if (queue === undefined || waiters === undefined) {
    throw new Error("socket messages were not tracked before connecting");
  }

  const deadline = Date.now() + 2_000;
  while (Date.now() < deadline) {
    const index = queue.findIndex(predicate);
    if (index >= 0) return queue.splice(index, 1)[0]!;
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(() => {
        waiters.delete(wake);
        resolve();
      }, 25);
      const wake = () => {
        clearTimeout(timeout);
        waiters.delete(wake);
        resolve();
      };
      waiters.add(wake);
    });
  }
  throw new Error(`expected websocket message; received ${JSON.stringify(queue)}`);
};

const trackedConnect = async (origin: string, token: string): Promise<WebSocket> => {
  const socket = new WebSocket(
    `${origin.replace("http", "ws")}/api/presentation-sync/ws?token=${token}`,
  );
  sockets.add(socket);
  trackMessages(socket);
  await once(socket, "open");
  return socket;
};

describe("presentation synchronization routes", () => {
  it("creates sessions and returns bounded validation and lookup errors", async () => {
    const { origin } = await startServer();

    const createdResponse = await postJson(origin, "/api/presentation-sync/sessions", {
      role: "presenter",
      initialHash: "#scene/planner-runtime/start",
    });
    expect(createdResponse.status).toBe(201);
    const created = (await createdResponse.json()) as SessionGrant;
    expect(created.sessionId).toBeTruthy();
    expect(created.code).toMatch(/^[A-Z0-9]{6}$/);
    expect(created.connectionToken).toBeTruthy();
    expect(created.websocketPath).toBe("/api/presentation-sync/ws");
    expect(created.snapshot.hash).toBe("#scene/planner-runtime/start");
    expect(created.snapshot.revision).toBe(0);

    const invalid = await postJson(origin, "/api/presentation-sync/sessions", {
      role: "presenter",
      initialHash: "https://example.test/not-a-presentation-hash",
    });
    expect(invalid.status).toBe(400);
    expect(await invalid.json()).toMatchObject({ error: { code: "invalid_request" } });

    const missing = await postJson(origin, "/api/presentation-sync/sessions/join", {
      role: "audience",
      code: "ABC123",
    });
    expect(missing.status).toBe(404);
    expect(await missing.json()).toMatchObject({ error: { code: "session_not_found" } });
  });

  it("synchronizes two real clients through reconnect and presenter shutdown", async () => {
    const { origin } = await startServer();
    const presenterGrant = await grant(origin, "/api/presentation-sync/sessions", {
      role: "presenter",
      initialHash: "#scene/planner-runtime/start",
    });
    const audienceGrant = await grant(origin, "/api/presentation-sync/sessions/join", {
      role: "audience",
      code: presenterGrant.code,
    });
    const presenter = await trackedConnect(origin, presenterGrant.connectionToken);
    const audience = await trackedConnect(origin, audienceGrant.connectionToken);

    await expectMessage(
      presenter,
      (message) => message.type === "location.snapshot" && message.snapshot.revision === 0,
    );
    await expectMessage(
      audience,
      (message) => message.type === "location.snapshot" && message.snapshot.revision === 0,
    );
    await expectMessage(
      presenter,
      (message) =>
        message.type === "presence.snapshot" && message.presence.audience === 1,
    );
    await expectMessage(
      audience,
      (message) =>
        message.type === "presence.snapshot" && message.presence.presenters === 1,
    );

    presenter.send(JSON.stringify({
      type: "location.publish",
      hash: "#scene/planner-runtime/boundary",
      baseRevision: 0,
      messageId: "p-1",
    }));
    await expectMessage(audience, (message) =>
      message.type === "location.snapshot" && message.snapshot.revision === 1
    );

    audience.send(JSON.stringify({
      type: "location.publish",
      hash: "#discuss/planner-runtime/question",
      baseRevision: 1,
      messageId: "a-1",
    }));
    await expectMessage(
      presenter,
      (message) => message.type === "location.snapshot" && message.snapshot.revision === 2,
    );

    presenter.send(JSON.stringify({
      type: "location.publish",
      hash: "#scene/planner-runtime/stale",
      baseRevision: 0,
      messageId: "p-stale",
    }));
    const rejected = await expectMessage(
      presenter,
      (message) => message.type === "location.rejected",
    );
    expect(rejected).toMatchObject({
      current: { hash: "#discuss/planner-runtime/question", revision: 2 },
      messageId: "p-stale",
    });

    const replacedClose = once(audience, "close");
    const reconnectedAudience = await trackedConnect(origin, audienceGrant.connectionToken);
    expect((await replacedClose)[0]).toBe(4001);
    await expectMessage(
      reconnectedAudience,
      (message) => message.type === "location.snapshot" && message.snapshot.revision === 2,
    );

    reconnectedAudience.send("not json");
    await expectMessage(
      reconnectedAudience,
      (message) => message.type === "protocol.error" && message.code === "invalid_message",
    );
    reconnectedAudience.send(JSON.stringify({ type: "session.end" }));
    await expectMessage(
      reconnectedAudience,
      (message) => message.type === "protocol.error" && message.code === "forbidden",
    );

    const endedClose = once(reconnectedAudience, "close");
    presenter.send(JSON.stringify({ type: "session.end" }));
    await expectMessage(
      reconnectedAudience,
      (message) => message.type === "session.ended" && message.reason === "presenter_ended",
    );
    expect((await endedClose)[0]).toBe(1000);
  });

  it("rejects oversized and binary frames without crashing later rooms", async () => {
    const { origin } = await startServer();
    const first = await grant(origin, "/api/presentation-sync/sessions", {
      role: "presenter",
      initialHash: "#scene/first",
    });
    const oversized = await trackedConnect(origin, first.connectionToken);
    const oversizedClose = once(oversized, "close");
    oversized.send("x".repeat(MAX_SYNC_MESSAGE_BYTES + 1));
    await expectMessage(
      oversized,
      (message) => message.type === "protocol.error" && message.code === "message_too_large",
    );
    expect((await oversizedClose)[0]).toBe(1009);

    const second = await grant(origin, "/api/presentation-sync/sessions", {
      role: "presenter",
      initialHash: "#scene/second",
    });
    const binary = await trackedConnect(origin, second.connectionToken);
    const binaryClose = once(binary, "close");
    binary.send(Buffer.from([1, 2, 3]));
    await expectMessage(
      binary,
      (message) => message.type === "protocol.error" && message.code === "invalid_message",
    );
    expect((await binaryClose)[0]).toBe(1003);

    const healthy = await grant(origin, "/api/presentation-sync/sessions", {
      role: "presenter",
      initialHash: "#scene/healthy",
    });
    const healthySocket = await trackedConnect(origin, healthy.connectionToken);
    await expectMessage(
      healthySocket,
      (message) => message.type === "location.snapshot" && message.snapshot.hash === "#scene/healthy",
    );
  });
});

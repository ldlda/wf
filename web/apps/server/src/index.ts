import { Effect } from "effect";
import {
  serve,
  upgradeWebSocket,
  type WebSocketServerLike,
} from "@hono/node-server";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import {
  WorkflowRpc,
  makeWorkflowRpcLayer,
  type OperationExchange,
  type OperationName,
} from "@lda/workflow-rpc";
import { createApp, type RunOperation } from "./app.js";
import { createPresentationRoomService } from "./presentation-sync/rooms.js";
import { shutdownServer } from "./shutdown.js";
import { WebSocketServer } from "ws";

const port = Number(process.env.WEB_PORT ?? "8787");
if (Number.isNaN(port) || port < 1 || port > 65535) {
  console.error(`Invalid WEB_PORT: ${process.env.WEB_PORT}`);
  process.exit(1);
}

const hostname = process.env.WEB_HOST ?? "127.0.0.1";

const liveLayer = makeWorkflowRpcLayer();
const consoleRoot = fileURLToPath(new URL("../../console/dist", import.meta.url));
const consoleIndex = path.join(consoleRoot, "index.html");
const staticConsoleRoot = fs.existsSync(consoleIndex) ? consoleRoot : undefined;
if (!staticConsoleRoot) {
  // In dev, Vite serves the console and proxies /api to this server. A missing
  // dist directory should not prevent the API proxy from starting.
  console.warn(`console dist not found; serving API only: ${consoleRoot}`);
}

const runOperation: RunOperation = async (
  operation: OperationName,
  target: string,
  params: unknown,
): Promise<OperationExchange> =>
  Effect.gen(function* () {
    const { execute } = yield* WorkflowRpc;
    return yield* execute(operation, target, params);
  }).pipe(Effect.provide(liveLayer), Effect.runPromise);

let app: ReturnType<typeof createApp>;
const rooms = createPresentationRoomService();
const wss = new WebSocketServer({ noServer: true });
try {
  app = createApp({
    runOperation,
    presentationSync: { rooms, upgradeWebSocket },
    ...(staticConsoleRoot ? { consoleRoot: staticConsoleRoot } : {}),
  });
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Failed to start workflow console server: ${message}`);
  process.exit(1);
}

const server = serve({
  fetch: app.fetch,
  hostname,
  port,
  // @types/ws makes noServer optional even though this instance fixes it to true.
  websocket: { server: wss as WebSocketServerLike },
});

// Rooms are intentionally in-memory; this sweep enforces reconnect grace and
// inactivity expiry without introducing persistence into the transport layer.
const expirySweep = setInterval(() => rooms.sweepExpired(), 60_000);
expirySweep.unref();

console.log(`workflow console server listening on http://${hostname}:${port}`);

let shuttingDown = false;
const shutdown = (signal: NodeJS.Signals) => {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`received ${signal}, stopping workflow console server`);
  clearInterval(expirySweep);
  shutdownServer({ server, wss, exit: (code) => process.exit(code) });
};

process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);

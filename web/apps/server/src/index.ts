import { Effect } from "effect";
import { serve } from "@hono/node-server";
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
try {
  app = createApp({
    runOperation,
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
});

console.log(`workflow console server listening on http://${hostname}:${port}`);

const shutdown = (signal: NodeJS.Signals) => {
  console.log(`received ${signal}, stopping workflow console server`);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 5_000).unref();
};

process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);

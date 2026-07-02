import { Effect, Layer } from "effect";
import { serve } from "@hono/node-server";
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

const liveLayer = makeWorkflowRpcLayer;

const runOperation: RunOperation = async (
  operation: OperationName,
  target: string,
  params: unknown,
): Promise<OperationExchange> =>
  Effect.gen(function* () {
    const { execute } = yield* WorkflowRpc;
    return yield* execute(operation, target, params);
  }).pipe(Effect.provide(liveLayer), Effect.runPromise);

const app = createApp({ runOperation });

serve({
  fetch: app.fetch,
  hostname,
  port,
});

console.log(`workflow console server listening on http://${hostname}:${port}`);

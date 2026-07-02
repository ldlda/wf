import { Effect, Either } from "effect";
import { describe, expect, it } from "vitest";
import { WorkflowRpc, makeWorkflowRpcLayer } from "./service.js";

const LIVE = process.env.LIVE_PYTHON_SERVER === "1";
const describeLive = LIVE ? describe : describe.skip;

const TARGET = "http://127.0.0.1:8765/rpc";

const runOperation = (operation: string, params: unknown = {}) =>
  Effect.gen(function* () {
    const rpc = yield* WorkflowRpc;
    return yield* rpc.execute(operation, TARGET, params);
  }).pipe(Effect.provide(makeWorkflowRpcLayer()), Effect.runPromise);

describeLive("interop: live Python server", () => {
  it("workflow.health returns interpreted status and raw JSON-RPC evidence", async () => {
    const exchange = await runOperation("workflow.health");

    expect(exchange.interpreted).toMatchObject({
      status: "ok",
      storeRoot: expect.any(String),
    });
    expect(exchange.exchange.request).toMatchObject({
      jsonrpc: "2.0",
      method: "workflow.health",
    });
    expect(exchange.exchange.response).toMatchObject({
      jsonrpc: "2.0",
      result: { status: "ok" },
    });
  });

  it("workflow.sources.list returns paginated interpreted results", async () => {
    const exchange = await runOperation("workflow.sources.list", { limit: 10 });

    expect(exchange.interpreted).toMatchObject({
      sources: expect.any(Array),
      total: expect.any(Number),
    });
    expect(exchange.equivalentCli).toContain("uv run wf source list");
  });

  it("unknown operations fail before reaching the server", async () => {
    const result = await Effect.gen(function* () {
      const rpc = yield* WorkflowRpc;
      return yield* rpc
        .execute("workflow.nope", TARGET, {})
        .pipe(Effect.either);
    }).pipe(Effect.provide(makeWorkflowRpcLayer()), Effect.runPromise);

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isLeft(result)) {
      expect(result.left._tag).toBe("UnknownOperationError");
    }
  });
});

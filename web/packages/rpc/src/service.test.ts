import { Effect, Either } from "effect";
import { describe, expect, it } from "vitest";
import {
  RpcDecodeError,
  RpcProtocolError,
  RpcRemoteError,
  UpstreamConnectionError,
  UpstreamResponseTooLargeError,
  UpstreamTimeoutError,
} from "./errors.js";
import {
  WorkflowRpc,
  makeWorkflowRpcLayer,
  type OperationExchange,
  type WorkflowRpcOptions,
} from "./service.js";

type JsonRpcRequest = {
  readonly jsonrpc: "2.0";
  readonly id: number | string;
  readonly method: string;
  readonly params: unknown;
};

const bodyText = async (
  body: RequestInit["body"] | null | undefined,
): Promise<string> => {
  if (typeof body === "string") return body;
  if (body instanceof Uint8Array) return new TextDecoder().decode(body);
  if (body instanceof Blob) return body.text();
  if (body instanceof ReadableStream) return new Response(body).text();
  throw new Error("expected JSON-RPC request body");
};

const requestBody = async (
  input: Parameters<typeof globalThis.fetch>[0],
  init?: RequestInit,
): Promise<JsonRpcRequest> => {
  if (input instanceof Request) {
    return JSON.parse(await input.clone().text()) as JsonRpcRequest;
  }

  return JSON.parse(await bodyText(init?.body ?? null)) as JsonRpcRequest;
};

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

const runOperation = (
  options: WorkflowRpcOptions,
  operation: "workflow.health" | "workflow.sources.list" = "workflow.health",
  params: unknown = {},
): Promise<OperationExchange> =>
  Effect.gen(function* () {
    const rpc = yield* WorkflowRpc;
    return yield* rpc.execute(
      operation,
      "http://127.0.0.1:8765/rpc",
      params,
    );
  }).pipe(Effect.provide(makeWorkflowRpcLayer(options)), Effect.runPromise);

const runEither = (
  options: WorkflowRpcOptions,
): Promise<Either.Either<OperationExchange, unknown>> =>
  Effect.gen(function* () {
    const rpc = yield* WorkflowRpc;
    return yield* rpc
      .execute("workflow.health", "http://127.0.0.1:8765/rpc", {})
      .pipe(Effect.either);
  }).pipe(Effect.provide(makeWorkflowRpcLayer(options)), Effect.runPromise);

const lifecycleCases = [
  {
    operation: "workflow.artifacts.list" as const,
    params: { limit: 50 },
    result: {
      nodes: [
        {
          name: "workflow.report@1",
          artifact_id: "report",
          version: 1,
          kind: "workflow",
          display_name: "Report",
          description: null,
          outcomes: ["ok"],
          input_schema: { type: "object" },
          output_schema: { type: "object" },
          required_sources: ["local.report"],
          diagnostics: [],
        },
      ],
      total: 1,
      next_cursor: null,
      limit: 50,
    },
  },
  {
    operation: "workflow.artifacts.inspect" as const,
    params: { artifact_id: "report", version: 1 },
    result: {
      id: "report",
      version: 1,
      title: "Report",
      kind: "workflow",
      description: null,
      outcomes: ["ok"],
      input_schema: { type: "object" },
      output_schema: { type: "object" },
      plan: { nodes: [], edges: [] },
      required_capabilities: [],
      workflow_dependencies: {},
      created_from_catalog_version: null,
    },
  },
  {
    operation: "workflow.deployments.list" as const,
    params: {},
    result: {
      deployments: [
        {
          id: "report.default",
          artifact_id: "report",
          artifact_version: 1,
          binding_count: 1,
          drift_policy: "block",
        },
      ],
    },
  },
  {
    operation: "workflow.deployments.inspect" as const,
    params: { deployment_id: "report.default" },
    result: {
      id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      bindings: [{ logical_source: "local.report", concrete_source: "report" }],
      drift_policy: "block",
    },
  },
  {
    operation: "workflow.deployments.validate" as const,
    params: { deployment_id: "report.default" },
    result: {
      deployment_id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      status: "runnable",
      diagnostics: [],
      next_actions: {
        can_continue: true,
        can_save_now: null,
        recommended_next_tool: null,
        reason: "deployment is valid",
        patch_examples: [],
        warnings: [],
      },
    },
  },
  {
    operation: "workflow.runs.list" as const,
    params: { limit: 50 },
    result: {
      runs: [
        {
          run_id: "run_1",
          deployment_id: "report.default",
          artifact_id: "report",
          artifact_version: 1,
          status: "interrupted",
          resume_readiness: "ready",
          diagnostic_count: 0,
          created_at: "2026-07-02T00:00:00Z",
          updated_at: "2026-07-02T00:00:01Z",
        },
      ],
      total: 1,
      cursor: null,
      next_cursor: null,
      limit: 50,
    },
  },
  {
    operation: "workflow.runs.inspect" as const,
    params: { run_id: "run_1" },
    result: {
      run_id: "run_1",
      deployment_id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      status: "interrupted",
      resume_readiness: "ready",
      interrupt: { kind: "review", payload: {}, outcomes: [] },
      outcome: null,
      error: null,
      output: null,
      diagnostics: [],
      trace_count: 0,
      next_actions: {
        can_continue: false,
        can_save_now: null,
        recommended_next_tool: null,
        reason: "run is interrupted",
        patch_examples: [],
        warnings: [],
      },
    },
  },
  {
    operation: "workflow.runs.trace" as const,
    params: { run_id: "run_1", trace_range: { start: 0, limit: 50 } },
    result: {
      run_id: "run_1",
      status: "interrupted",
      trace_start: 0,
      trace_limit: 50,
      trace_truncated: false,
      trace: [
        {
          node_id: "review",
          step_type: "interrupt",
          resolved_input: { report: "..." },
          outcome: "submitted",
          output: {},
          state_changes: {},
        },
      ],
    },
  },
] as const;

describe("WorkflowRpc", () => {
  it("uses @effect/rpc and returns exact raw request and response evidence", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: { status: "ok", store_root: "C:/store" },
      });
    };

    const exchange = await runOperation({ fetch });

    expect(exchange.target).toBe("http://127.0.0.1:8765/rpc");
    expect(exchange.interpreted).toEqual({
      status: "ok",
      storeRoot: "C:/store",
    });
    expect(exchange.exchange.request).toMatchObject({
      jsonrpc: "2.0",
      method: "workflow.health",
      params: {},
    });
    expect(exchange.exchange.response).toMatchObject({
      jsonrpc: "2.0",
      result: { status: "ok", store_root: "C:/store" },
    });
  });

  it("requests manual redirect handling", async () => {
    let redirect: RequestInit["redirect"];
    const fetch: typeof globalThis.fetch = async (input, init) => {
      redirect = init?.redirect ?? (input instanceof Request ? input.redirect : undefined);
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: { status: "ok", store_root: "C:/store" },
      });
    };

    await runOperation({ fetch });

    expect(redirect).toBe("manual");
  });

  it("maps a standard foreign JSON-RPC error and preserves evidence", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        error: { code: -32602, message: "Invalid params", data: { field: "x" } },
      });
    };

    const result = await runEither({ fetch });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcRemoteError);
    expect((result.left as RpcRemoteError).exchange?.response).toMatchObject({
      error: { code: -32602, message: "Invalid params" },
    });
  });

  it("maps malformed successful results to decode errors with evidence", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: { status: "wrong", store_root: "C:/store" },
      });
    };

    const result = await runEither({ fetch });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcDecodeError);
    expect((result.left as RpcDecodeError).exchange?.response).toMatchObject({
      result: { status: "wrong", store_root: "C:/store" },
    });
  });

  it("rejects invalid source count shapes as decode errors", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: {
          sources: [
            {
              id: "local.demo",
              kind: "python",
              enabled: true,
              description: null,
              tool_count: -1,
              node_spec_count: 0,
              reducer_count: 0,
              prompt_count: 0,
              resource_count: 0,
            },
          ],
          next_cursor: null,
          total: 1,
        },
      });
    };

    const result = await Effect.gen(function* () {
      const rpc = yield* WorkflowRpc;
      return yield* rpc
        .execute(
          "workflow.sources.list",
          "http://127.0.0.1:8765/rpc",
          {},
        )
        .pipe(Effect.either);
    }).pipe(Effect.provide(makeWorkflowRpcLayer({ fetch })), Effect.runPromise);

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcDecodeError);
  });

  it("fails with a bounded timeout", async () => {
    const fetch: typeof globalThis.fetch = () => new Promise<Response>(() => {});

    const result = await runEither({ fetch, timeoutMilliseconds: 5 });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(UpstreamTimeoutError);
  });

  it("maps transport failures to upstream connection errors", async () => {
    const fetch: typeof globalThis.fetch = async () => {
      throw new Error("connection refused");
    };

    const result = await runEither({ fetch });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(UpstreamConnectionError);
  });

  it("rejects a response larger than the configured byte limit", async () => {
    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: { status: "ok", store_root: "x".repeat(512) },
      });
    };

    const result = await runEither({ fetch, maxResponseBytes: 128 });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(UpstreamResponseTooLargeError);
  });

  it("rejects a redirect response instead of decoding it", async () => {
    const fetch: typeof globalThis.fetch = async () =>
      new Response("", { status: 302, headers: { location: "/elsewhere" } });

    const result = await runEither({ fetch });

    expect(Either.isLeft(result)).toBe(true);
    if (Either.isRight(result)) return;
    expect(result.left).toBeInstanceOf(RpcProtocolError);
  });
});

describe("lifecycle operations", () => {
  for (const testCase of lifecycleCases) {
    it(`handles ${testCase.operation} successfully`, async () => {
      const fetch: typeof globalThis.fetch = async (input, init) => {
        const request = await requestBody(input, init);
        expect(request.method).toBe(testCase.operation);
        return jsonResponse({
          jsonrpc: "2.0",
          id: request.id,
          result: testCase.result,
        });
      };

      const exchange = await runOperation(
        { fetch },
        testCase.operation as "workflow.health" | "workflow.sources.list",
        testCase.params,
      );

      expect(exchange.operation).toBe(testCase.operation);
      expect(exchange.interpreted).toBeDefined();
    });
  }

  it("interprets run trace frames with the console lifecycle shape", async () => {
    const traceCase = lifecycleCases.find(
      (testCase) => testCase.operation === "workflow.runs.trace",
    );
    expect(traceCase).toBeDefined();
    if (!traceCase) return;

    const fetch: typeof globalThis.fetch = async (input, init) => {
      const request = await requestBody(input, init);
      return jsonResponse({
        jsonrpc: "2.0",
        id: request.id,
        result: traceCase.result,
      });
    };

    const exchange = await runOperation(
      { fetch },
      traceCase.operation as "workflow.health" | "workflow.sources.list",
      traceCase.params,
    );

    expect(exchange.interpreted).toMatchObject({
      frames: [
        {
          nodeId: "review",
          stepType: "interrupt",
          outcome: "submitted",
        },
      ],
      traceStart: 0,
      traceLimit: 50,
      traceTruncated: false,
    });
    expect(exchange.interpreted).not.toHaveProperty("trace");
  });
});

import { Effect, Either } from "effect";
import { describe, expect, it } from "vitest";
import {
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

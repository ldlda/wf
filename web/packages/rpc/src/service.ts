import { Context, Effect, Layer, Ref } from "effect";
import { RpcClient, RpcGroup, RpcSerialization } from "@effect/rpc";
import { FetchHttpClient, HttpClient } from "@effect/platform";
import { normalizeLoopbackTarget } from "./target-policy.js";
import { getOperationMeta } from "./method-registry.js";
import { WorkflowHealth, WorkflowSourcesList, WorkflowRpcs } from "./rpcs.js";
import { withEvidenceCapture, type EvidenceRecord } from "./evidence.js";
import {
  InvalidTargetError,
  UnknownOperationError,
  UpstreamConnectionError,
  UpstreamTimeoutError,
  RpcProtocolError,
  RpcRemoteError,
} from "./errors.js";

export interface OperationExchange {
  readonly operation: string;
  readonly label: string;
  readonly interpreted: unknown;
  readonly exchange: { readonly request: unknown; readonly response: unknown };
  readonly equivalentCli: string;
  readonly durationMs: number;
}

export type WorkflowRpcError =
  | InvalidTargetError
  | UnknownOperationError
  | UpstreamConnectionError
  | UpstreamTimeoutError
  | RpcProtocolError
  | RpcRemoteError;

export type OperationName = "workflow.health" | "workflow.sources.list";

const isOperationName = (s: string): s is OperationName =>
  s === "workflow.health" || s === "workflow.sources.list";

const rpcsByTag = new Map(
  [WorkflowHealth, WorkflowSourcesList].map((r) => [r._tag, r] as const),
);

const interpretResult = (operation: string, result: unknown): unknown => {
  const meta = getOperationMeta(operation);
  return meta ? meta.interpret(result) : result;
};

/**
 * Map an Effect failure cause to our domain errors.
 *
 * Handles both Effect-native errors (RequestError, ResponseError) and
 * foreign JSON-RPC errors from the Python server (which lack Effect's
 * Cause shape). For foreign errors, we read the captured raw response
 * evidence to extract the JSON-RPC error object.
 */
const mapCauseToError = (
  cause: unknown,
  evidence: EvidenceRecord | null,
): WorkflowRpcError => {
  if (
    cause &&
    typeof cause === "object" &&
    "_tag" in cause &&
    typeof cause._tag === "string"
  ) {
    const tag = cause._tag;
    if (tag === "RequestError" || tag === "HttpClientError") {
      const err = "error" in cause ? cause.error : undefined;
      const msg = err instanceof Error ? err.message : String(cause);
      if (msg.toLowerCase().includes("timeout")) {
        return new UpstreamTimeoutError({ message: msg });
      }
      return new UpstreamConnectionError({ message: msg });
    }
    if (tag === "ResponseError") {
      const err = "error" in cause ? cause.error : undefined;
      const msg = err instanceof Error ? err.message : String(cause);
      return new UpstreamConnectionError({ message: msg });
    }
  }

  // Foreign JSON-RPC error: extract from captured raw response evidence
  if (evidence?.response?.body) {
    const body = evidence.response.body;
    if (typeof body === "object" && body !== null && "error" in body) {
      const rpcErr = (body as { error: unknown }).error;
      if (typeof rpcErr === "object" && rpcErr !== null) {
        const errObj = rpcErr as {
          message?: unknown;
          code?: unknown;
          data?: unknown;
        };
        return new RpcRemoteError({
          message: String(errObj.message ?? "remote error"),
          code: Number(errObj.code ?? -1),
          ...(errObj.data != null ? { data: String(errObj.data) } : {}),
        });
      }
    }
  }

  const msg = cause instanceof Error ? cause.message : String(cause);
  return new RpcProtocolError({ message: msg });
};

export const WorkflowRpc = Context.GenericTag<{
  readonly execute: (
    operation: string,
    target: string,
    params: unknown,
  ) => Effect.Effect<OperationExchange, WorkflowRpcError>;
}>("WorkflowRpc");

/**
 * Dispatch an RPC call through a typed client.
 *
 * The `client` is the result of `RpcClient.make(group)` which has typed
 * methods like `client["workflow.health"]({})`. We use a dispatch map
 * to avoid unsafe casts.
 */
const dispatchRpc = (
  client: WorkflowRpcsClient,
  operation: OperationName,
  params: unknown,
): Effect.Effect<unknown> => {
  switch (operation) {
    case "workflow.health":
      return client["workflow.health"](params as Record<string, never>);
    case "workflow.sources.list":
      return client["workflow.sources.list"](
        params as { cursor?: string; limit?: number },
      );
  }
};

// The typed client shape produced by RpcClient.make(WorkflowRpcs)
type WorkflowRpcsClient = {
  readonly "workflow.health": (
    input: Record<string, never>,
  ) => Effect.Effect<{ readonly status: "ok"; readonly store_root: string }>;
  readonly "workflow.sources.list": (input: {
    cursor?: string;
    limit?: number;
  }) => Effect.Effect<{
    readonly sources: ReadonlyArray<{
      readonly id: string;
      readonly kind: string;
      readonly enabled: boolean;
      readonly description: string | null;
      readonly tool_count: number;
      readonly node_spec_count: number;
      readonly reducer_count: number;
      readonly prompt_count: number;
      readonly resource_count: number;
    }>;
    readonly next_cursor: string | null;
    readonly total: number;
  }>;
};

const executeImpl = (
  operation: string,
  target: string,
  params: unknown,
): Effect.Effect<OperationExchange, WorkflowRpcError> => {
  let normalizedTarget: string;
  try {
    normalizedTarget = normalizeLoopbackTarget(target);
  } catch (e) {
    return Effect.fail(
      e instanceof InvalidTargetError
        ? e
        : new InvalidTargetError({
            message: e instanceof Error ? e.message : String(e),
          }),
    );
  }

  const meta = getOperationMeta(operation);
  if (!meta) {
    return Effect.fail(
      new UnknownOperationError({
        message: `unknown operation: ${operation}`,
      }),
    );
  }

  if (!isOperationName(operation)) {
    return Effect.fail(
      new UnknownOperationError({
        message: `unsupported operation: ${operation}`,
      }),
    );
  }

  const evidenceRef = Ref.unsafeMake<EvidenceRecord | null>(null);

  return Effect.gen(function* () {
    const startTime = Date.now();

    const rpcDef = rpcsByTag.get(operation)!;
    const group = RpcGroup.make(rpcDef);

    const rpcClient = yield* RpcClient.make(group);
    const result: unknown = yield* dispatchRpc(
      rpcClient as unknown as WorkflowRpcsClient,
      operation,
      params,
    );

    const evidenceVal = yield* Ref.get(evidenceRef);

    if (
      result &&
      typeof result === "object" &&
      "_tag" in result &&
      result._tag === "Left"
    ) {
      const left = (result as unknown as { left: unknown }).left;
      return yield* Effect.fail(mapCauseToError(left, evidenceVal));
    }

    const successValue =
      result &&
      typeof result === "object" &&
      "_tag" in result &&
      result._tag === "Right"
        ? (result as unknown as { right: unknown }).right
        : result;

    const interpreted = interpretResult(operation, successValue);
    const durationMs = Date.now() - startTime;

    return {
      operation,
      label: meta.label,
      interpreted,
      exchange: {
        request: evidenceVal?.request?.body ?? params,
        response: evidenceVal?.response?.body ?? successValue,
      },
      equivalentCli: meta.equivalentCli(params),
      durationMs,
    };
  }).pipe(
    Effect.provide(
      RpcClient.layerProtocolHttp({
        url: normalizedTarget,
        transformClient: (c) => withEvidenceCapture(c, evidenceRef),
      }).pipe(
        Layer.provide(
          Layer.mergeAll(FetchHttpClient.layer, RpcSerialization.layerJsonRpc()),
        ),
      ),
    ),
    Effect.scoped,
  );
};

export const makeWorkflowRpcLayer = Layer.succeed(WorkflowRpc, {
  execute: executeImpl,
});

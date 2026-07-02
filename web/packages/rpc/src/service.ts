import { FetchHttpClient } from "@effect/platform";
import { RpcClient, RpcSerialization } from "@effect/rpc";
import {
  Cause,
  Clock,
  Context,
  Effect,
  Layer,
  Option,
  Ref,
  Schema,
} from "effect";
import {
  InvalidTargetError,
  RpcDecodeError,
  type RpcExchangeEvidence,
  RpcProtocolError,
  RpcRemoteError,
  UnknownOperationError,
  UpstreamConnectionError,
  UpstreamResponseTooLargeError,
  UpstreamTimeoutError,
} from "./errors.js";
import { type EvidenceRecord, withEvidenceCapture } from "./evidence.js";
import { getOperationMeta } from "./method-registry.js";
import {
  WorkflowHealthPayloadSchema,
  WorkflowRpcs,
  WorkflowSourcesListPayloadSchema,
  WorkflowArtifactsListPayloadSchema,
  WorkflowArtifactsInspectPayloadSchema,
  WorkflowDeploymentsListPayloadSchema,
  WorkflowDeploymentsInspectPayloadSchema,
  WorkflowDeploymentsValidatePayloadSchema,
  WorkflowRunsListPayloadSchema,
  WorkflowRunsInspectPayloadSchema,
  WorkflowRunsStartPayloadSchema,
  WorkflowRunsResumePayloadSchema,
  WorkflowRunsTracePayloadSchema,
} from "./rpcs.js";
import { normalizeLoopbackTarget } from "./target-policy.js";

const DEFAULT_TIMEOUT_MILLISECONDS = 5_000;
const DEFAULT_MAX_RESPONSE_BYTES = 4 * 1024 * 1024;

export type OperationName =
  | "workflow.health"
  | "workflow.sources.list"
  | "workflow.artifacts.list"
  | "workflow.artifacts.inspect"
  | "workflow.deployments.list"
  | "workflow.deployments.inspect"
  | "workflow.deployments.validate"
  | "workflow.runs.list"
  | "workflow.runs.inspect"
  | "workflow.runs.start"
  | "workflow.runs.resume"
  | "workflow.runs.trace";

export interface WorkflowRpcOptions {
  readonly fetch?: typeof globalThis.fetch;
  readonly timeoutMilliseconds?: number;
  readonly maxResponseBytes?: number;
}

export interface OperationExchange {
  readonly operation: OperationName;
  readonly target: string;
  readonly label: string;
  readonly interpreted: unknown;
  readonly exchange: RpcExchangeEvidence;
  readonly equivalentCli: string;
  readonly durationMs: number;
}

export type WorkflowRpcError =
  | InvalidTargetError
  | UnknownOperationError
  | UpstreamConnectionError
  | UpstreamTimeoutError
  | UpstreamResponseTooLargeError
  | RpcProtocolError
  | RpcRemoteError
  | RpcDecodeError;

const isOperationName = (value: string): value is OperationName =>
  value === "workflow.health" ||
  value === "workflow.sources.list" ||
  value === "workflow.artifacts.list" ||
  value === "workflow.artifacts.inspect" ||
  value === "workflow.deployments.list" ||
  value === "workflow.deployments.inspect" ||
  value === "workflow.deployments.validate" ||
  value === "workflow.runs.list" ||
  value === "workflow.runs.inspect" ||
  value === "workflow.runs.start" ||
  value === "workflow.runs.resume" ||
  value === "workflow.runs.trace";

const toExchange = (evidence: EvidenceRecord | null): RpcExchangeEvidence => ({
  request: evidence?.request.body ?? null,
  response: evidence?.response?.body ?? null,
});

const responseError = (
  evidence: EvidenceRecord | null,
): { readonly code: number; readonly message: string; readonly data?: unknown } | null => {
  const body = evidence?.response?.body;
  if (typeof body !== "object" || body === null || !("error" in body)) return null;
  const error = body.error;
  if (typeof error !== "object" || error === null) return null;
  const code = "code" in error ? Number(error.code) : Number.NaN;
  const message = "message" in error ? String(error.message) : "remote error";
  if (!Number.isFinite(code)) return null;
  return {
    code,
    message,
    ...("data" in error ? { data: error.data } : {}),
  };
};

const containsTag = (
  value: unknown,
  tags: ReadonlySet<string>,
  depth = 0,
): boolean => {
  if (depth > 6 || typeof value !== "object" || value === null) return false;
  if ("_tag" in value && typeof value._tag === "string" && tags.has(value._tag)) {
    return true;
  }
  return Object.values(value).some((child) => containsTag(child, tags, depth + 1));
};

const domainErrorFromUnknown = (
  value: unknown,
  exchange: RpcExchangeEvidence,
): WorkflowRpcError | null => {
  if (value instanceof UpstreamTimeoutError) {
    return new UpstreamTimeoutError({ message: value.message, exchange });
  }
  if (value instanceof UpstreamResponseTooLargeError) {
    return new UpstreamResponseTooLargeError({ message: value.message, exchange });
  }
  if (value instanceof RpcProtocolError) {
    return new RpcProtocolError({ message: value.message, exchange });
  }
  if (value instanceof RpcDecodeError) {
    return new RpcDecodeError({ message: value.message, exchange });
  }
  return null;
};

const mapCauseToError = (
  cause: Cause.Cause<unknown>,
  evidence: EvidenceRecord | null,
): WorkflowRpcError => {
  const exchange = toExchange(evidence);
  const remote = responseError(evidence);
  if (remote) {
    return new RpcRemoteError({
      message: remote.message,
      code: remote.code,
      ...(remote.data === undefined ? {} : { data: JSON.stringify(remote.data) }),
      exchange,
    });
  }

  const failure = Option.getOrUndefined(Cause.failureOption(cause));
  const defect = Option.getOrUndefined(Cause.dieOption(cause));
  const known =
    domainErrorFromUnknown(failure, exchange) ??
    domainErrorFromUnknown(defect, exchange);
  if (known) return known;

  if (evidence?.request && !evidence.response) {
    return new UpstreamConnectionError({
      message: "could not connect to the workflow RPC server",
      exchange,
    });
  }

  if (containsTag(cause, new Set(["RequestError", "ResponseError"]))) {
    return new UpstreamConnectionError({
      message: "could not connect to the workflow RPC server",
      exchange,
    });
  }

  const description = String(Cause.squash(cause));
  const lowerDescription = description.toLowerCase();
  if (
    lowerDescription.includes("parse") ||
    lowerDescription.includes("schema") ||
    lowerDescription.includes("decode") ||
    lowerDescription.includes("expected")
  ) {
    return new RpcDecodeError({
      message: "workflow RPC result did not match the expected schema",
      exchange,
    });
  }
  return new RpcProtocolError({
    message: "workflow RPC server returned an invalid response",
    exchange,
  });
};

const decodeParams = <A, I>(
  schema: Schema.Schema<A, I>,
  params: unknown,
): Effect.Effect<A, RpcDecodeError> =>
  Schema.decodeUnknown(schema, { onExcessProperty: "error" })(params).pipe(
    Effect.mapError(
      () => new RpcDecodeError({ message: "invalid workflow RPC parameters" }),
    ),
  );

const decodeOperationMetadata = (
  metadata: NonNullable<ReturnType<typeof getOperationMeta>>,
  result: unknown,
  params: unknown,
  evidence: EvidenceRecord | null,
): Effect.Effect<
  { readonly interpreted: unknown; readonly equivalentCli: string },
  RpcDecodeError
> =>
  Effect.try({
    try: () => ({
      interpreted: metadata.interpret(result),
      equivalentCli: metadata.equivalentCli(params),
    }),
    catch: () =>
      new RpcDecodeError({
        message: "workflow RPC result did not match the expected schema",
        exchange: toExchange(evidence),
      }),
  });

const executeImpl =
  (options: WorkflowRpcOptions) =>
  (
    operation: string,
    target: string,
    params: unknown,
  ): Effect.Effect<OperationExchange, WorkflowRpcError> => {
    let normalizedTarget: string;
    try {
      normalizedTarget = normalizeLoopbackTarget(target);
    } catch (error) {
      return Effect.fail(
        error instanceof InvalidTargetError
          ? error
          : new InvalidTargetError({ message: "invalid workflow RPC target" }),
      );
    }
    if (!isOperationName(operation)) {
      return Effect.fail(
        new UnknownOperationError({ message: `unknown operation: ${operation}` }),
      );
    }

    return Effect.gen(function* () {
      const evidenceRef = yield* Ref.make<EvidenceRecord | null>(null);
      const startedAt = yield* Clock.currentTimeMillis;
      const timeoutMilliseconds =
        options.timeoutMilliseconds ?? DEFAULT_TIMEOUT_MILLISECONDS;
      const maxResponseBytes =
        options.maxResponseBytes ?? DEFAULT_MAX_RESPONSE_BYTES;

      const fetchOptionsLayer = Layer.mergeAll(
        Layer.succeed(FetchHttpClient.Fetch, options.fetch ?? globalThis.fetch),
        Layer.succeed(FetchHttpClient.RequestInit, { redirect: "manual" }),
      );
      const fetchLayer = Layer.merge(
        FetchHttpClient.layer.pipe(Layer.provide(fetchOptionsLayer)),
        RpcSerialization.layerJsonRpc(),
      );
      const protocolLayer = RpcClient.layerProtocolHttp({
        url: normalizedTarget,
        transformClient: (client) =>
          withEvidenceCapture(client, evidenceRef, maxResponseBytes),
      }).pipe(Layer.provide(fetchLayer));

      const call = Effect.gen(function* () {
        const client = yield* RpcClient.make(WorkflowRpcs);
        switch (operation) {
          case "workflow.health": {
            const payload = yield* decodeParams(WorkflowHealthPayloadSchema, params);
            return yield* client.workflow.health(payload);
          }
          case "workflow.sources.list": {
            const payload = yield* decodeParams(
              WorkflowSourcesListPayloadSchema,
              params,
            );
            return yield* client.workflow["sources.list"](payload);
          }
          case "workflow.artifacts.list": {
            const payload = yield* decodeParams(
              WorkflowArtifactsListPayloadSchema,
              params,
            );
            return yield* client.workflow["artifacts.list"](payload);
          }
          case "workflow.artifacts.inspect": {
            const payload = yield* decodeParams(
              WorkflowArtifactsInspectPayloadSchema,
              params,
            );
            return yield* client.workflow["artifacts.inspect"](payload);
          }
          case "workflow.deployments.list": {
            const payload = yield* decodeParams(
              WorkflowDeploymentsListPayloadSchema,
              params,
            );
            return yield* client.workflow["deployments.list"](payload);
          }
          case "workflow.deployments.inspect": {
            const payload = yield* decodeParams(
              WorkflowDeploymentsInspectPayloadSchema,
              params,
            );
            return yield* client.workflow["deployments.inspect"](payload);
          }
          case "workflow.deployments.validate": {
            const payload = yield* decodeParams(
              WorkflowDeploymentsValidatePayloadSchema,
              params,
            );
            return yield* client.workflow["deployments.validate"](payload);
          }
          case "workflow.runs.list": {
            const payload = yield* decodeParams(
              WorkflowRunsListPayloadSchema,
              params,
            );
            return yield* client.workflow["runs.list"](payload);
          }
          case "workflow.runs.inspect": {
            const payload = yield* decodeParams(
              WorkflowRunsInspectPayloadSchema,
              params,
            );
            return yield* client.workflow["runs.inspect"](payload);
          }
          case "workflow.runs.start": {
            const payload = yield* decodeParams(
              WorkflowRunsStartPayloadSchema,
              params,
            );
            return yield* client.workflow["runs.start"](payload);
          }
          case "workflow.runs.resume": {
            const payload = yield* decodeParams(
              WorkflowRunsResumePayloadSchema,
              params,
            );
            return yield* client.workflow["runs.resume"](payload);
          }
          case "workflow.runs.trace": {
            const payload = yield* decodeParams(
              WorkflowRunsTracePayloadSchema,
              params,
            );
            return yield* client.workflow["runs.trace"](payload);
          }
        }
      }).pipe(
        Effect.provide(protocolLayer),
        Effect.scoped,
        Effect.timeoutFail({
          duration: timeoutMilliseconds,
          onTimeout: () =>
            new UpstreamTimeoutError({
              message: "workflow RPC request timed out",
            }),
        }),
        Effect.catchAllCause((cause) =>
          Ref.get(evidenceRef).pipe(
            Effect.flatMap((evidence) => Effect.fail(mapCauseToError(cause, evidence))),
          ),
        ),
      );

      const result = yield* call;
      const evidence = yield* Ref.get(evidenceRef);
      const metadata = getOperationMeta(operation);
      if (!metadata) {
        return yield* Effect.fail(
          new UnknownOperationError({ message: `unknown operation: ${operation}` }),
        );
      }
      const decodedMetadata = yield* decodeOperationMetadata(
        metadata,
        result,
        params,
        evidence,
      );
      const finishedAt = yield* Clock.currentTimeMillis;
      return {
        operation,
        target: normalizedTarget,
        label: metadata.label,
        interpreted: decodedMetadata.interpreted,
        exchange: toExchange(evidence),
        equivalentCli: decodedMetadata.equivalentCli,
        durationMs: finishedAt - startedAt,
      };
    });
  };

export const WorkflowRpc = Context.GenericTag<{
  readonly execute: (
    operation: string,
    target: string,
    params: unknown,
  ) => Effect.Effect<OperationExchange, WorkflowRpcError>;
}>("WorkflowRpc");

export const makeWorkflowRpcLayer = (options: WorkflowRpcOptions = {}) =>
  Layer.succeed(WorkflowRpc, { execute: executeImpl(options) });

import * as v from "valibot";

const KnownBrowserErrorCodeSchema = v.union([
  v.literal("invalid_target"),
  v.literal("unknown_operation"),
  v.literal("upstream_unreachable"),
  v.literal("upstream_timeout"),
  v.literal("rpc_remote_error"),
  v.literal("rpc_protocol_error"),
  v.literal("rpc_decode_error"),
  v.literal("response_too_large"),
]);
const BrowserErrorCodeSchema = v.union([KnownBrowserErrorCodeSchema, v.string()]);

const ExchangeSchema = v.object({
  request: v.nullish(v.unknown(), null),
  response: v.nullish(v.unknown(), null),
});

const ApiFailureSchema = v.object({
  ok: v.literal(false),
  error: v.object({
    code: BrowserErrorCodeSchema,
    message: v.string(),
  }),
  exchange: ExchangeSchema,
});

const ConnectionSuccessSchema = v.object({
  ok: v.literal(true),
  connection: v.object({
    status: v.literal("connected"),
    target: v.string(),
    serverStatus: v.literal("ok"),
    storeRoot: v.string(),
    durationMs: v.number(),
  }),
  exchange: ExchangeSchema,
  equivalentCli: v.string(),
});

const OperationNameSchema = v.union([
  v.literal("workflow.health"),
  v.literal("workflow.sources.list"),
]);

const OperationSuccessSchema = v.object({
  ok: v.literal(true),
  operation: OperationNameSchema,
  label: v.string(),
  interpreted: v.unknown(),
  exchange: ExchangeSchema,
  equivalentCli: v.string(),
  durationMs: v.number(),
});

const ConnectResponseSchema = v.union([ConnectionSuccessSchema, ApiFailureSchema]);
const RpcResponseSchema = v.union([OperationSuccessSchema, ApiFailureSchema]);

export type ConnectionSuccess = v.InferOutput<typeof ConnectionSuccessSchema>;
export type OperationSuccess = v.InferOutput<typeof OperationSuccessSchema>;
export type BrowserErrorCode = v.InferOutput<typeof BrowserErrorCodeSchema>;
export type ApiFailure = v.InferOutput<typeof ApiFailureSchema>;
export type ConnectResponse = v.InferOutput<typeof ConnectResponseSchema>;
export type RpcResponse = v.InferOutput<typeof RpcResponseSchema>;
export type OperationName = v.InferOutput<typeof OperationNameSchema>;

const parseDto = <T>(schema: v.GenericSchema<unknown, T>, data: unknown): T => {
  try {
    return v.parse(schema, data);
  } catch (error) {
    const details = error instanceof Error ? `: ${error.message}` : "";
    throw new Error(`malformed response from server${details}`);
  }
};

export const parseConnectResponse = (data: unknown): ConnectResponse =>
  parseDto(ConnectResponseSchema, data);

export const parseRpcResponse = (data: unknown): RpcResponse =>
  parseDto(RpcResponseSchema, data);

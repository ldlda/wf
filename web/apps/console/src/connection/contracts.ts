export type ConnectionSuccess = {
  readonly ok: true;
  readonly connection: {
    readonly status: "connected";
    readonly target: string;
    readonly serverStatus: "ok";
    readonly storeRoot: string;
    readonly durationMs: number;
  };
  readonly exchange: { readonly request: unknown; readonly response: unknown };
  readonly equivalentCli: string;
};

export type OperationSuccess = {
  readonly ok: true;
  readonly operation: string;
  readonly label: string;
  readonly interpreted: unknown;
  readonly exchange: { readonly request: unknown; readonly response: unknown };
  readonly equivalentCli: string;
  readonly durationMs: number;
};

export type BrowserErrorCode =
  | "invalid_target"
  | "unknown_operation"
  | "upstream_unreachable"
  | "upstream_timeout"
  | "rpc_remote_error"
  | "rpc_protocol_error"
  | "rpc_decode_error"
  | "response_too_large";

export type ApiFailure = {
  readonly ok: false;
  readonly error: { readonly code: BrowserErrorCode; readonly message: string };
  readonly exchange: {
    readonly request: unknown | null;
    readonly response: unknown | null;
  };
};

export type ConnectResponse = ConnectionSuccess | ApiFailure;
export type RpcResponse = OperationSuccess | ApiFailure;

export type OperationName = "workflow.health" | "workflow.sources.list";

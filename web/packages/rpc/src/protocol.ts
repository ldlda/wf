import { Schema } from "effect";
import { RpcDecodeError, RpcProtocolError } from "./errors.js";

export { RpcDecodeError, RpcProtocolError };

const JsonRpcVersion = Schema.Literal("2.0");

const JsonRpcErrorObject = Schema.Struct({
  code: Schema.Number,
  message: Schema.String,
  data: Schema.optional(Schema.String),
});

const decodeJsonRpcVersion = Schema.decodeUnknownSync(JsonRpcVersion);
const decodeErrorObject = Schema.decodeUnknownSync(JsonRpcErrorObject);

export type JsonRpcRequest = {
  readonly jsonrpc: "2.0";
  readonly id: string;
  readonly method: string;
  readonly params: unknown;
};

export type JsonRpcSuccess = {
  readonly jsonrpc: "2.0";
  readonly id: string;
  readonly result: unknown;
};

export type JsonRpcFailure = {
  readonly jsonrpc: "2.0";
  readonly id: string;
  readonly error: {
    readonly code: number;
    readonly message: string;
    readonly data?: string;
  };
};

export type JsonRpcResponse = JsonRpcSuccess | JsonRpcFailure;

function throwRpcDecode(message: string): never {
  throw new RpcDecodeError({ message });
}

export function decodeRpcResponse(
  value: unknown,
  expectedId: string,
): JsonRpcResponse {
  if (typeof value !== "object" || value === null) {
    throwRpcDecode("response must be a JSON object");
  }

  const obj = value as Record<string, unknown>;

  if (!("jsonrpc" in obj) || !("id" in obj)) {
    throwRpcDecode("response must contain 'jsonrpc' and 'id' fields");
  }

  try {
    decodeJsonRpcVersion(obj.jsonrpc, { onExcessProperty: "error" });
  } catch {
    throwRpcDecode(`jsonrpc version must be "2.0", got ${JSON.stringify(obj.jsonrpc)}`);
  }

  if (typeof obj.id !== "string") {
    throwRpcDecode(`response id must be a string, got ${typeof obj.id}`);
  }

  if (obj.id !== expectedId) {
    throw new RpcProtocolError({
      message: `response id "${obj.id}" does not match expected id "${expectedId}"`,
      evidence: JSON.stringify(obj),
    });
  }

  const hasResult = "result" in obj;
  const hasError = "error" in obj;

  if (hasResult && hasError) {
    throwRpcDecode("response must not contain both 'result' and 'error'");
  }

  if (!hasResult && !hasError) {
    throwRpcDecode("response must contain exactly one of 'result' or 'error'");
  }

  if (hasResult) {
    return { jsonrpc: "2.0", id: obj.id, result: obj.result };
  }

  if (typeof obj.error !== "object" || obj.error === null) {
    throwRpcDecode("'error' must be an object");
  }

  let errorObj: { readonly code: number; readonly message: string; readonly data?: string | undefined };
  try {
    errorObj = decodeErrorObject(obj.error, { onExcessProperty: "error" });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throwRpcDecode(`invalid error object: ${msg}`);
  }

  const error: { code: number; message: string; data?: string } = {
    code: errorObj.code,
    message: errorObj.message,
  };
  if (errorObj.data !== undefined) {
    error.data = errorObj.data;
  }

  return { jsonrpc: "2.0", id: obj.id, error };
}

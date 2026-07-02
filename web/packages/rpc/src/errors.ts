import { Data } from "effect";

export type RpcExchangeEvidence = {
  readonly request: unknown | null;
  readonly response: unknown | null;
};

export class InvalidTargetError extends Data.TaggedError("InvalidTargetError")<{
  readonly message: string;
}> {}

export class UnknownOperationError extends Data.TaggedError(
  "UnknownOperationError",
)<{
  readonly message: string;
}> {}

export class UpstreamConnectionError extends Data.TaggedError(
  "UpstreamConnectionError",
)<{
  readonly message: string;
  readonly exchange?: RpcExchangeEvidence;
}> {}

export class UpstreamTimeoutError extends Data.TaggedError(
  "UpstreamTimeoutError",
)<{
  readonly message: string;
  readonly exchange?: RpcExchangeEvidence;
}> {}

export class UpstreamResponseTooLargeError extends Data.TaggedError(
  "UpstreamResponseTooLargeError",
)<{
  readonly message: string;
  readonly exchange?: RpcExchangeEvidence;
}> {}

export class RpcProtocolError extends Data.TaggedError("RpcProtocolError")<{
  readonly message: string;
  readonly exchange?: RpcExchangeEvidence;
}> {}

export class RpcRemoteError extends Data.TaggedError("RpcRemoteError")<{
  readonly message: string;
  readonly code: number;
  readonly data?: string;
  readonly exchange?: RpcExchangeEvidence;
}> {}

export class RpcDecodeError extends Data.TaggedError("RpcDecodeError")<{
  readonly message: string;
  readonly exchange?: RpcExchangeEvidence;
}> {}

import { callOperation } from "../../connection/api.js";
import type {
  OperationName,
  RpcResponse,
} from "../../connection/contracts.js";
import type { EvidenceRecord } from "../../app/state.js";
import { ConsoleClientError, type ConsoleClientErrorKind } from "./errors.js";

export interface ConsoleReadExecutor {
  run<T>(
    operation: OperationName,
    params: unknown,
    decode: (value: unknown) => T,
  ): Promise<T>;
}

type InvokeOperation = (
  operation: OperationName,
  target: string,
  params: unknown,
) => Promise<RpcResponse>;

const errorKindForCode = (code: string): ConsoleClientErrorKind => {
  switch (code) {
    case "invalid_target":
    case "upstream_unreachable":
      return "connection";
    case "unknown_operation":
      return "permission";
    case "rpc_decode_error":
      return "decode";
    default:
      return "operation";
  }
};

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

export const createConsoleReadExecutor = (options: {
  readonly target: string;
  readonly recordEvidence: (record: EvidenceRecord) => void;
  readonly invoke?: InvokeOperation;
}): ConsoleReadExecutor => {
  let evidenceSequence = 0;
  const invoke = options.invoke ?? callOperation;

  const record = (
    operation: OperationName,
    label: string,
    equivalentCli: string,
    request: unknown,
    response: unknown,
    durationMs: number,
  ): void => {
    options.recordEvidence({
      id: `${operation}-${evidenceSequence++}`,
      operation,
      label,
      equivalentCli,
      request,
      response,
      durationMs,
    });
  };

  return {
    async run<T>(
      operation: OperationName,
      params: unknown,
      decode: (value: unknown) => T,
    ): Promise<T> {
      let response: RpcResponse;
      try {
        response = await invoke(operation, options.target, params);
      } catch (error) {
        record(
          operation,
          `${operation} failed`,
          "unavailable: operation failed before CLI metadata",
          null,
          null,
          0,
        );
        throw new ConsoleClientError(
          "transport",
          operation,
          errorMessage(error),
        );
      }

      if (!response.ok) {
        record(
          operation,
          `${operation} failed`,
          "unavailable: operation failed before CLI metadata",
          response.exchange.request,
          response.exchange.response,
          0,
        );
        throw new ConsoleClientError(
          errorKindForCode(response.error.code),
          operation,
          response.error.message,
        );
      }

      record(
        response.operation,
        response.label,
        response.equivalentCli,
        response.exchange.request,
        response.exchange.response,
        response.durationMs,
      );

      try {
        return decode(response.interpreted);
      } catch (error) {
        throw new ConsoleClientError(
          "decode",
          operation,
          errorMessage(error),
        );
      }
    },
  };
};

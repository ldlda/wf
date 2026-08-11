import { callOperation, ConsoleApiError } from "../../connection/api.js";
import type {
  OperationName,
  RpcResponse,
} from "../../connection/contracts.js";
import type { EvidenceRecord } from "../../app/state.js";
import { ConsoleClientError, type ConsoleClientErrorKind } from "./errors.js";

export interface ConsoleExecutor {
  run<T>(
    operation: OperationName,
    params: unknown,
    decode: (value: unknown) => T,
  ): Promise<T>;
}

export type ConsoleExecutorOptions = {
  readonly target: string;
  readonly recordEvidence: (record: EvidenceRecord) => void;
  readonly allocateEvidenceId?: (operation: string) => string;
  readonly shouldRecordEvidence?: () => boolean;
  readonly invoke?: (
    operation: OperationName,
    target: string,
    params: unknown,
  ) => Promise<RpcResponse>;
};

const errorKindForCode = (code: string): ConsoleClientErrorKind => {
  switch (code) {
    case "invalid_target":
    case "upstream_unreachable":
      return "connection";
    case "unknown_operation":
      return "operation";
    case "rpc_decode_error":
      return "decode";
    default:
      return "operation";
  }
};

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const clientErrorKindForInvocation = (
  error: unknown,
): "decode" | "transport" =>
  error instanceof ConsoleApiError && error.kind !== "transport"
    ? "decode"
    : "transport";

/** Keeps read and write executors on one evidence/error protocol. */
export const createConsoleExecutor = (
  options: ConsoleExecutorOptions,
): ConsoleExecutor => {
  let evidenceSequence = 0;
  const invoke = options.invoke ?? callOperation;
  const allocateEvidenceId =
    options.allocateEvidenceId ??
    ((operation: string): string => `${operation}-${evidenceSequence++}`);

  const record = (
    operation: OperationName,
    label: string,
    equivalentCli: string,
    request: unknown,
    response: unknown,
    durationMs: number,
  ): void => {
    if (options.shouldRecordEvidence?.() === false) return;
    options.recordEvidence({
      id: allocateEvidenceId(operation),
      target: options.target,
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
      const startedAt = performance.now();
      const durationSinceStart = (): number =>
        Math.max(0, Math.round(performance.now() - startedAt));

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
          durationSinceStart(),
        );
        throw new ConsoleClientError(
          clientErrorKindForInvocation(error),
          operation,
          errorMessage(error),
          { cause: error },
        );
      }

      if (!response.ok) {
        record(
          operation,
          `${operation} failed`,
          "unavailable: operation failed before CLI metadata",
          response.exchange.request,
          response.exchange.response,
          durationSinceStart(),
        );
        throw new ConsoleClientError(
          errorKindForCode(response.error.code),
          operation,
          response.error.message,
        );
      }

      if (response.operation !== operation) {
        record(
          operation,
          `${operation} failed`,
          "unavailable: response operation mismatch",
          response.exchange.request,
          response.exchange.response,
          response.durationMs,
        );
        throw new ConsoleClientError(
          "operation",
          operation,
          `operation mismatch: requested ${operation}, received ${response.operation}`,
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
          { cause: error },
        );
      }
    },
  };
};

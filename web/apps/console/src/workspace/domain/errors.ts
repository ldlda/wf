import type { OperationName } from "../../connection/contracts.js";

export type ConsoleClientErrorKind =
  | "connection"
  | "not_found"
  | "permission"
  | "decode"
  | "transport"
  | "operation";

export class ConsoleClientError extends Error {
  override readonly name = "ConsoleClientError";

  constructor(
    readonly kind: ConsoleClientErrorKind,
    readonly operation: OperationName,
    message: string,
  ) {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

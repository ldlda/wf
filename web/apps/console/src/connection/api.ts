import type {
  ConnectResponse,
  RpcResponse,
  OperationName,
} from "./contracts.js";
import { parseConnectResponse, parseRpcResponse } from "./contracts.js";

export type ConsoleApiErrorKind = "transport" | "protocol" | "decode";

export class ConsoleApiError extends Error {
  override readonly name = "ConsoleApiError";

  constructor(
    readonly kind: ConsoleApiErrorKind,
    message: string,
  ) {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const fetchJson = async <T>(
  url: string,
  init: RequestInit,
  parse: (data: unknown) => T,
): Promise<T> => {
  let res: Response;
  let text: string;
  try {
    res = await fetch(url, init);
    text = await res.text();
  } catch (error) {
    throw new ConsoleApiError("transport", errorMessage(error));
  }
  if (!text) {
    throw new ConsoleApiError(
      "protocol",
      `console backend returned an empty response (HTTP ${res.status})`,
    );
  }
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new ConsoleApiError("protocol", "malformed JSON response from server");
  }
  try {
    return parse(data);
  } catch (error) {
    throw new ConsoleApiError("decode", errorMessage(error));
  }
};

export const connectToServer = async (
  target: string,
): Promise<ConnectResponse> =>
  fetchJson(
    "/api/connect",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ target }),
    },
    parseConnectResponse,
  );

export const callOperation = async (
  operation: OperationName,
  target: string,
  params: unknown = {},
): Promise<RpcResponse> =>
  fetchJson(
    "/api/rpc",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ operation, target, params }),
    },
    parseRpcResponse,
  );

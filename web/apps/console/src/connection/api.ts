import type {
  ConnectResponse,
  RpcResponse,
  OperationName,
} from "./contracts.js";
import { parseConnectResponse, parseRpcResponse } from "./contracts.js";

const fetchJson = async <T>(
  url: string,
  init: RequestInit,
  parse: (data: unknown) => T,
): Promise<T> => {
  const res = await fetch(url, init);
  const text = await res.text();
  if (!text) {
    throw new Error(
      `console backend returned an empty response (HTTP ${res.status})`,
    );
  }
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("malformed JSON response from server");
  }
  return parse(data);
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

import type {
  ConnectResponse,
  RpcResponse,
  OperationName,
} from "./contracts.js";

const fetchJson = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const res = await fetch(url, init);
  const text = await res.text();
  if (!text) {
    throw new Error("empty response from server");
  }
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("malformed JSON response from server");
  }
  return data as T;
};

export const connectToServer = async (
  target: string,
): Promise<ConnectResponse> =>
  fetchJson<ConnectResponse>("/api/connect", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ target }),
  });

export const callOperation = async (
  operation: OperationName,
  target: string,
  params: unknown = {},
): Promise<RpcResponse> =>
  fetchJson<RpcResponse>("/api/rpc", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ operation, target, params }),
  });

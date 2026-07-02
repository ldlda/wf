import { describe, expect, it } from "vitest";
import { RpcDecodeError, RpcProtocolError, decodeRpcResponse } from "./protocol.js";

describe("decodeRpcResponse", () => {
  it("decodes success envelope with matching string id", () => {
    const payload = {
      jsonrpc: "2.0",
      id: "req-1",
      result: { status: "ok" },
    };
    expect(decodeRpcResponse(payload, "req-1")).toEqual({
      jsonrpc: "2.0",
      id: "req-1",
      result: { status: "ok" },
    });
  });

  it("decodes error envelope with matching string id", () => {
    const payload = {
      jsonrpc: "2.0",
      id: "req-1",
      error: { code: -32000, message: "server error" },
    };
    const response = decodeRpcResponse(payload, "req-1");
    expect(response).toEqual({
      jsonrpc: "2.0",
      id: "req-1",
      error: { code: -32000, message: "server error" },
    });
  });

  it("rejects mismatched id", () => {
    const payload = {
      jsonrpc: "2.0",
      id: "other",
      result: { status: "ok" },
    };
    expect(() => decodeRpcResponse(payload, "req-1")).toThrow(
      RpcProtocolError,
    );
  });

  it("rejects envelope with both result and error", () => {
    const payload = {
      jsonrpc: "2.0",
      id: "req-1",
      result: { status: "ok" },
      error: { code: -32000, message: "err" },
    };
    expect(() => decodeRpcResponse(payload, "req-1")).toThrow(RpcDecodeError);
  });

  it("rejects envelope with neither result nor error", () => {
    const payload = {
      jsonrpc: "2.0",
      id: "req-1",
    };
    expect(() => decodeRpcResponse(payload, "req-1")).toThrow(RpcDecodeError);
  });

  it("rejects wrong jsonrpc version", () => {
    const payload = {
      jsonrpc: "1.0",
      id: "req-1",
      result: {},
    };
    expect(() => decodeRpcResponse(payload, "req-1")).toThrow(RpcDecodeError);
  });

  it("rejects malformed error object", () => {
    const payload = {
      jsonrpc: "2.0",
      id: "req-1",
      error: { message: "missing code" },
    };
    expect(() => decodeRpcResponse(payload, "req-1")).toThrow(RpcDecodeError);
  });

  it("rejects non-object payload", () => {
    expect(() => decodeRpcResponse("not an object", "req-1")).toThrow(
      RpcDecodeError,
    );
  });
});

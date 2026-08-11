import { describe, expect, it } from "vitest";
import { parseRpcResponse } from "./contracts.js";

describe("connection contracts", () => {
  it("accepts the operation_disabled browser error", () => {
    const response = parseRpcResponse({
      ok: false,
      error: {
        code: "operation_disabled",
        message:
          "workflow.capabilities.call is disabled for this console server",
      },
      exchange: { request: null, response: null },
    });

    expect(response.ok).toBe(false);
    if (!response.ok) {
      expect(response.error.code).toBe("operation_disabled");
    }
  });
});

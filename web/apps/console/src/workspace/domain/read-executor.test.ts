import { describe, expect, it, vi } from "vitest";
import { ConsoleApiError } from "../../connection/api.js";
import type { RpcResponse } from "../../connection/contracts.js";
import { createConsoleReadExecutor } from "./read-executor.js";

const success = (interpreted: unknown): RpcResponse => ({
  ok: true,
  operation: "workflow.capabilities.list",
  label: "List capabilities",
  interpreted,
  exchange: { request: { sent: true }, response: { status: 200 } },
  equivalentCli: "uv run wf cap list",
  durationMs: 4,
});

const failure = (code: string): RpcResponse => ({
  ok: false,
  error: { code, message: "operation failed" },
  exchange: { request: { sent: true }, response: { status: 502 } },
});

describe("ConsoleReadExecutor", () => {
  it("records one receipt and returns decoded success data", async () => {
    const invoke = vi.fn(async () => success({ value: 1 }));
    const recordEvidence = vi.fn();
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke,
    });

    const result = await executor.run(
      "workflow.capabilities.list",
      { limit: 1 },
      (value) => ({ decoded: value }),
    );

    expect(result).toEqual({ decoded: { value: 1 } });
    expect(invoke).toHaveBeenCalledWith(
      "workflow.capabilities.list",
      "http://console.test/rpc",
      { limit: 1 },
    );
    expect(recordEvidence).toHaveBeenCalledTimes(1);
    expect(recordEvidence.mock.calls[0]?.[0]).toMatchObject({
      id: "workflow.capabilities.list-0",
      operation: "workflow.capabilities.list",
      request: { sent: true },
      response: { status: 200 },
    });
  });

  it("records failed evidence and normalizes browser failures", async () => {
    const recordEvidence = vi.fn();
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => failure("upstream_unreachable")),
    });

    await expect(
      executor.run("workflow.capabilities.list", {}, (value) => value),
    ).rejects.toMatchObject({
      kind: "connection",
      operation: "workflow.capabilities.list",
    });
    expect(recordEvidence).toHaveBeenCalledTimes(1);
    expect(recordEvidence.mock.calls[0]?.[0]).toMatchObject({
      id: "workflow.capabilities.list-0",
      label: "workflow.capabilities.list failed",
      response: { status: 502 },
    });
  });

  it("turns decoder failures into decode errors", async () => {
    const recordEvidence = vi.fn();
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => success({ malformed: true })),
    });

    await expect(
      executor.run("workflow.capabilities.list", {}, () => {
        throw new Error("invalid capability page");
      }),
    ).rejects.toMatchObject({ kind: "decode" });
    expect(recordEvidence).toHaveBeenCalledTimes(1);
  });

  it("maps rejected invocations to transport errors", async () => {
    const recordEvidence = vi.fn();
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => {
        throw new Error("fetch failed");
      }),
    });

    await expect(
      executor.run("workflow.capabilities.list", {}, (value) => value),
    ).rejects.toMatchObject({ kind: "transport" });
    expect(recordEvidence).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["protocol", "malformed JSON response"],
    ["decode", "malformed response from server"],
  ] as const)(
    "maps typed %s invocation failures to decode errors",
    async (kind, message) => {
      const recordEvidence = vi.fn();
      const executor = createConsoleReadExecutor({
        target: "http://console.test/rpc",
        recordEvidence,
        invoke: vi.fn(async () => {
          throw new ConsoleApiError(kind, message);
        }),
      });

      await expect(
        executor.run("workflow.capabilities.list", {}, (value) => value),
      ).rejects.toMatchObject({ kind: "decode", message });
      expect(recordEvidence).toHaveBeenCalledTimes(1);
    },
  );

  it("keeps evidence ids unique across consecutive reads", async () => {
    const recordEvidence = vi.fn();
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => success(null)),
    });

    await executor.run("workflow.capabilities.list", {}, (value) => value);
    await executor.run("workflow.capabilities.list", {}, (value) => value);

    const ids = recordEvidence.mock.calls.map(([record]) => record.id);
    expect(new Set(ids).size).toBe(2);
  });
});

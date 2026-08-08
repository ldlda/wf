import { describe, expect, it, vi } from "vitest";
import { ConsoleApiError } from "../../connection/api.js";
import type { OperationName, RpcResponse } from "../../connection/contracts.js";
import { createConsoleReadExecutor } from "./read-executor.js";

const success = (
  interpreted: unknown,
  operation: OperationName = "workflow.capabilities.list",
): RpcResponse => ({
  ok: true,
  operation,
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

  it("maps unknown browser operations to operation errors", async () => {
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence: vi.fn(),
      invoke: vi.fn(async () => failure("unknown_operation")),
    });

    await expect(
      executor.run("workflow.capabilities.list", {}, (value) => value),
    ).rejects.toMatchObject({
      kind: "operation",
      operation: "workflow.capabilities.list",
    });
  });

  it("rejects a successful response for a different requested operation", async () => {
    const recordEvidence = vi.fn();
    const decode = vi.fn((value: unknown) => value);
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () =>
        success(null, "workflow.draft_workspaces.list"),
      ),
    });

    await expect(
      executor.run("workflow.capabilities.list", {}, decode),
    ).rejects.toMatchObject({
      kind: "operation",
      operation: "workflow.capabilities.list",
      message: "operation mismatch: requested workflow.capabilities.list, received workflow.draft_workspaces.list",
    });
    expect(decode).not.toHaveBeenCalled();
    expect(recordEvidence).toHaveBeenCalledTimes(1);
    expect(recordEvidence.mock.calls[0]?.[0]).toMatchObject({
      operation: "workflow.capabilities.list",
      label: "workflow.capabilities.list failed",
      equivalentCli: "unavailable: response operation mismatch",
    });
  });

  it("turns decoder failures into decode errors", async () => {
    const recordEvidence = vi.fn();
    const cause = new Error("invalid capability page");
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => success({ malformed: true })),
    });

    await expect(
      executor.run("workflow.capabilities.list", {}, () => {
        throw cause;
      }),
    ).rejects.toMatchObject({ kind: "decode", cause });
    expect(recordEvidence).toHaveBeenCalledTimes(1);
  });

  it("maps rejected invocations to transport errors", async () => {
    const recordEvidence = vi.fn();
    const cause = new Error("fetch failed");
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => {
        throw cause;
      }),
    });

    await expect(
      executor.run("workflow.capabilities.list", {}, (value) => value),
    ).rejects.toMatchObject({ kind: "transport", cause });
    expect(recordEvidence).toHaveBeenCalledTimes(1);
  });

  it("measures duration for failures before operation metadata exists", async () => {
    const now = vi
      .spyOn(performance, "now")
      .mockReturnValueOnce(100)
      .mockReturnValueOnce(137);
    const recordEvidence = vi.fn();
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => failure("upstream_unreachable")),
    });

    await expect(
      executor.run("workflow.capabilities.list", {}, (value) => value),
    ).rejects.toMatchObject({ kind: "connection" });

    expect(recordEvidence.mock.calls[0]?.[0]?.durationMs).toBe(37);
    now.mockRestore();
  });

  it("measures duration for rejected invocations before operation metadata exists", async () => {
    const now = vi
      .spyOn(performance, "now")
      .mockReturnValueOnce(200)
      .mockReturnValueOnce(249);
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

    expect(recordEvidence.mock.calls[0]?.[0]?.durationMs).toBe(49);
    now.mockRestore();
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

  it("uses a caller-owned allocator when evidence spans executor lifetimes", async () => {
    const recordEvidence = vi.fn();
    const allocateEvidenceId = vi.fn((operation: string) => `workspace-${operation}`);
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      allocateEvidenceId,
      invoke: vi.fn(async () => success(null)),
    });

    await executor.run("workflow.capabilities.list", {}, (value) => value);

    expect(allocateEvidenceId).toHaveBeenCalledWith("workflow.capabilities.list");
    expect(recordEvidence.mock.calls[0]?.[0]?.id).toBe(
      "workspace-workflow.capabilities.list",
    );
  });

  it("does not record evidence when its connection generation is stale", async () => {
    const recordEvidence = vi.fn();
    const executor = createConsoleReadExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      shouldRecordEvidence: () => false,
      invoke: vi.fn(async () => success(null)),
    });

    await executor.run("workflow.capabilities.list", {}, (value) => value);

    expect(recordEvidence).not.toHaveBeenCalled();
  });
});

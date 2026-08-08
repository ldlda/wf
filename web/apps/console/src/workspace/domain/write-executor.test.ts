import { describe, expect, it, vi } from "vitest";
import { ConsoleApiError } from "../../connection/api.js";
import type { OperationName, RpcResponse } from "../../connection/contracts.js";
import { createConsoleWriteExecutor } from "./write-executor.js";

const createSuccess = (
  interpreted: unknown,
  operation: OperationName = "workflow.draft_workspaces.create_empty",
): RpcResponse => ({
  ok: true,
  operation,
  label: "Create empty draft workspace",
  interpreted,
  exchange: { request: { sent: true }, response: { status: 200 } },
  equivalentCli: "uv run wf draft create draft-report --name report",
  durationMs: 4,
});

const createFailure = (code: string): RpcResponse => ({
  ok: false,
  error: { code, message: "operation failed" },
  exchange: { request: { sent: true }, response: { status: 502 } },
});

describe("ConsoleWriteExecutor", () => {
  it("records one receipt and returns decoded mutation data", async () => {
    const invoke = vi.fn(async () => createSuccess({ revision: 2 }));
    const recordEvidence = vi.fn();
    const executor = createConsoleWriteExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke,
    });

    const result = await executor.run(
      "workflow.draft_workspaces.create_empty",
      { workspace_id: "draft-report" },
      (value) => ({ decoded: value }),
    );

    expect(result).toEqual({ decoded: { revision: 2 } });
    expect(invoke).toHaveBeenCalledWith(
      "workflow.draft_workspaces.create_empty",
      "http://console.test/rpc",
      { workspace_id: "draft-report" },
    );
    expect(recordEvidence).toHaveBeenCalledTimes(1);
    expect(recordEvidence.mock.calls[0]?.[0]).toMatchObject({
      id: "workflow.draft_workspaces.create_empty-0",
      operation: "workflow.draft_workspaces.create_empty",
      request: { sent: true },
      response: { status: 200 },
      durationMs: 4,
    });
  });

  it("records server failures and maps their error kind", async () => {
    const recordEvidence = vi.fn();
    const executor = createConsoleWriteExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => createFailure("upstream_unreachable")),
    });

    await expect(
      executor.run("workflow.draft_workspaces.validate", {}, (value) => value),
    ).rejects.toMatchObject({
      kind: "connection",
      operation: "workflow.draft_workspaces.validate",
    });
    expect(recordEvidence).toHaveBeenCalledTimes(1);
    expect(recordEvidence.mock.calls[0]?.[0]).toMatchObject({
      operation: "workflow.draft_workspaces.validate",
      label: "workflow.draft_workspaces.validate failed",
      response: { status: 502 },
    });
  });

  it("rejects an operation mismatch before decoding", async () => {
    const recordEvidence = vi.fn();
    const decode = vi.fn((value: unknown) => value);
    const executor = createConsoleWriteExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () =>
        createSuccess(
          null,
          "workflow.draft_workspaces.set_route",
        ),
      ),
    });

    await expect(
      executor.run("workflow.draft_workspaces.create_empty", {}, decode),
    ).rejects.toMatchObject({
      kind: "operation",
      message:
        "operation mismatch: requested workflow.draft_workspaces.create_empty, received workflow.draft_workspaces.set_route",
    });
    expect(decode).not.toHaveBeenCalled();
    expect(recordEvidence.mock.calls[0]?.[0]).toMatchObject({
      operation: "workflow.draft_workspaces.create_empty",
      equivalentCli: "unavailable: response operation mismatch",
    });
  });

  it("preserves decoder and transport causes", async () => {
    const decodeCause = new Error("invalid draft response");
    const decodeExecutor = createConsoleWriteExecutor({
      target: "http://console.test/rpc",
      recordEvidence: vi.fn(),
      invoke: vi.fn(async () => createSuccess({ malformed: true })),
    });

    await expect(
      decodeExecutor.run("workflow.draft_workspaces.create_empty", {}, () => {
        throw decodeCause;
      }),
    ).rejects.toMatchObject({ kind: "decode", cause: decodeCause });

    const transportCause = new Error("fetch failed");
    const transportExecutor = createConsoleWriteExecutor({
      target: "http://console.test/rpc",
      recordEvidence: vi.fn(),
      invoke: vi.fn(async () => {
        throw transportCause;
      }),
    });

    await expect(
      transportExecutor.run("workflow.draft_workspaces.create_empty", {}, (value) => value),
    ).rejects.toMatchObject({ kind: "transport", cause: transportCause });

    const protocolExecutor = createConsoleWriteExecutor({
      target: "http://console.test/rpc",
      recordEvidence: vi.fn(),
      invoke: vi.fn(async () => {
        throw new ConsoleApiError("protocol", "malformed JSON response");
      }),
    });
    await expect(
      protocolExecutor.run("workflow.draft_workspaces.create_empty", {}, (value) => value),
    ).rejects.toMatchObject({ kind: "decode" });
  });

  it("records elapsed duration for failures without response metadata", async () => {
    const now = vi
      .spyOn(performance, "now")
      .mockReturnValueOnce(100)
      .mockReturnValueOnce(137);
    const recordEvidence = vi.fn();
    const executor = createConsoleWriteExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      invoke: vi.fn(async () => createFailure("upstream_unreachable")),
    });

    await expect(
      executor.run("workflow.draft_workspaces.validate", {}, (value) => value),
    ).rejects.toMatchObject({ kind: "connection" });
    expect(recordEvidence.mock.calls[0]?.[0]?.durationMs).toBe(37);
    now.mockRestore();
  });

  it("suppresses evidence for a stale connection generation", async () => {
    const recordEvidence = vi.fn();
    const executor = createConsoleWriteExecutor({
      target: "http://console.test/rpc",
      recordEvidence,
      shouldRecordEvidence: () => false,
      invoke: vi.fn(async () => createSuccess(null)),
    });

    await executor.run("workflow.draft_workspaces.create_empty", {}, (value) => value);

    expect(recordEvidence).not.toHaveBeenCalled();
  });
});

import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ConnectionState } from "../../app/state.js";
import { useConsoleWorkspace } from "../context.js";
import {
  callCapability,
  type CapabilityCallRequest,
} from "../domain/capability-call-client.js";
import type { CapabilityCallResult } from "../domain/capability-models.js";
import type { ConsoleWriteExecutor } from "../domain/write-executor.js";
import { useCapabilityPlayground } from "./useCapabilityPlayground.js";

vi.mock("../context.js", () => ({
  useConsoleWorkspace: vi.fn(),
}));

vi.mock("../domain/capability-call-client.js", async () => {
  const actual = await vi.importActual<
    typeof import("../domain/capability-call-client.js")
  >("../domain/capability-call-client.js");
  return { ...actual, callCapability: vi.fn() };
});

const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCallCapability = vi.mocked(callCapability);

const connectedState = {
  phase: "connected",
  connectedTarget: "http://workflow.example/rpc",
} as ConnectionState;

const disconnectedState = {
  phase: "not_configured",
  connectedTarget: null,
} as ConnectionState;

const writeExecutor = {} as ConsoleWriteExecutor;

const result = (outcome = "ok"): CapabilityCallResult => ({
  qualifiedName: "local.docs.read_documents",
  sourceId: "local.docs",
  kind: "node_spec",
  deploymentId: null,
  outcome,
  output: outcome === "runtime_error" ? null : { documents: [] },
  diagnostics: [],
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

beforeEach(() => {
  mockedCallCapability.mockReset();
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: connectedState,
    connectedTarget: connectedState.connectedTarget,
    recordEvidence: vi.fn(),
    readExecutor: null,
    writeExecutor,
  });
});

describe("useCapabilityPlayground", () => {
  it("is disconnected without a connected write target", () => {
    mockedUseConsoleWorkspace.mockReturnValue({
      connection: disconnectedState,
      connectedTarget: null,
      recordEvidence: vi.fn(),
      readExecutor: null,
      writeExecutor: null,
    });

    const { result: hook } = renderHook(() =>
      useCapabilityPlayground("local.docs.read_documents"),
    );

    expect(hook.current.phase).toBe("disconnected");
    expect(hook.current.result).toBeNull();
  });

  it("starts connected in the idle phase", async () => {
    const { result: hook } = renderHook(() =>
      useCapabilityPlayground("local.docs.read_documents"),
    );

    await waitFor(() => expect(hook.current.phase).toBe("idle"));
    expect(hook.current.acknowledged).toBe(false);
    expect(hook.current.deploymentId).toBe("");
  });

  it("reports calling and then a successful result", async () => {
    mockedCallCapability.mockResolvedValue(result());
    const { result: hook } = renderHook(() =>
      useCapabilityPlayground("local.docs.read_documents"),
    );

    act(() => hook.current.call({ names: ["README.md"] }));
    expect(hook.current.phase).toBe("calling");
    await waitFor(() => expect(hook.current.phase).toBe("result"));
    expect(hook.current.result?.outcome).toBe("ok");
  });

  it("keeps runtime_error in the completed result phase", async () => {
    mockedCallCapability.mockResolvedValue(result("runtime_error"));
    const { result: hook } = renderHook(() =>
      useCapabilityPlayground("local.docs.read_documents"),
    );

    act(() => hook.current.call({}));

    await waitFor(() => expect(hook.current.phase).toBe("result"));
    expect(hook.current.result?.outcome).toBe("runtime_error");
    expect(hook.current.message).toBeNull();
  });

  it("reports transport and protocol failures as an error phase", async () => {
    mockedCallCapability.mockRejectedValue(new Error("upstream unavailable"));
    const { result: hook } = renderHook(() =>
      useCapabilityPlayground("local.docs.read_documents"),
    );

    act(() => hook.current.call({}));

    await waitFor(() => expect(hook.current.phase).toBe("error"));
    expect(hook.current.message).toBe("upstream unavailable");
    expect(hook.current.result).toBeNull();
  });

  it("suppresses a second submit while a call is pending", () => {
    const pending = deferred<CapabilityCallResult>();
    mockedCallCapability.mockReturnValue(pending.promise);
    const { result: hook } = renderHook(() =>
      useCapabilityPlayground("local.docs.read_documents"),
    );

    act(() => {
      hook.current.call({ first: true });
      hook.current.call({ second: true });
    });

    expect(mockedCallCapability).toHaveBeenCalledTimes(1);
  });

  it("resets acknowledgement, deployment, and result when capability changes", async () => {
    mockedCallCapability.mockResolvedValue(result());
    const { result: hook, rerender } = renderHook(
      ({ qualifiedName }) => useCapabilityPlayground(qualifiedName),
      { initialProps: { qualifiedName: "local.docs.read_documents" } },
    );

    act(() => {
      hook.current.setAcknowledged(true);
      hook.current.setDeploymentId("docs.default");
      hook.current.call({});
    });
    await waitFor(() => expect(hook.current.phase).toBe("result"));

    rerender({ qualifiedName: "local.docs.write_documents" });

    await waitFor(() => expect(hook.current.phase).toBe("idle"));
    expect(hook.current.acknowledged).toBe(false);
    expect(hook.current.deploymentId).toBe("");
    expect(hook.current.result).toBeNull();
  });

  it("resets and isolates a pending call when the connected target changes", async () => {
    const targetA = {} as ConsoleWriteExecutor;
    const targetB = {} as ConsoleWriteExecutor;
    const targetACall = deferred<CapabilityCallResult>();
    const targetBCall = deferred<CapabilityCallResult>();
    mockedCallCapability
      .mockReturnValueOnce(targetACall.promise)
      .mockReturnValueOnce(targetBCall.promise);
    mockedUseConsoleWorkspace.mockReturnValue({
      connection: connectedState,
      connectedTarget: "http://target-a.example/rpc",
      recordEvidence: vi.fn(),
      readExecutor: null,
      writeExecutor: targetA,
    });
    const { result: hook, rerender } = renderHook(() =>
      useCapabilityPlayground("local.docs.read_documents"),
    );

    await waitFor(() => expect(hook.current.phase).toBe("idle"));
    act(() => {
      hook.current.setAcknowledged(true);
      hook.current.setDeploymentId("target-a.default");
      hook.current.call({ target: "a" });
    });
    expect(hook.current.phase).toBe("calling");

    mockedUseConsoleWorkspace.mockReturnValue({
      connection: connectedState,
      connectedTarget: "http://target-b.example/rpc",
      recordEvidence: vi.fn(),
      readExecutor: null,
      writeExecutor: targetB,
    });
    rerender();

    expect(hook.current.phase).toBe("idle");
    expect(hook.current.acknowledged).toBe(false);
    expect(hook.current.deploymentId).toBe("");
    expect(hook.current.result).toBeNull();
    expect(hook.current.message).toBeNull();

    targetACall.reject(new Error("target A failed"));
    await Promise.resolve();
    expect(hook.current.phase).toBe("idle");
    expect(hook.current.message).toBeNull();
    expect(hook.current.result).toBeNull();

    act(() => hook.current.call({ target: "b" }));
    expect(hook.current.phase).toBe("calling");
    targetBCall.resolve({
      ...result(),
      qualifiedName: "local.docs.read_documents",
    });

    await waitFor(() => expect(hook.current.phase).toBe("result"));
    expect(hook.current.result?.outcome).toBe("ok");
    expect(mockedCallCapability).toHaveBeenLastCalledWith(targetB, {
      qualifiedName: "local.docs.read_documents",
      payload: { target: "b" },
      deploymentId: "",
    });
  });

  it("ignores a stale completion after the selected capability changes", async () => {
    const first = deferred<CapabilityCallResult>();
    const second = deferred<CapabilityCallResult>();
    mockedCallCapability
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const { result: hook, rerender } = renderHook(
      ({ qualifiedName }) => useCapabilityPlayground(qualifiedName),
      { initialProps: { qualifiedName: "local.docs.first" } },
    );

    act(() => hook.current.call({ value: "first" }));
    rerender({ qualifiedName: "local.docs.second" });
    act(() => hook.current.call({ value: "second" }));

    first.resolve({ ...result(), qualifiedName: "local.docs.first" });
    await waitFor(() => expect(hook.current.phase).toBe("calling"));
    second.resolve({ ...result(), qualifiedName: "local.docs.second" });

    await waitFor(() =>
      expect(hook.current.result?.qualifiedName).toBe("local.docs.second"),
    );
  });

  it("passes the selected capability, payload, and deployment to the client", async () => {
    mockedCallCapability.mockResolvedValue(result());
    const { result: hook } = renderHook(() =>
      useCapabilityPlayground("local.docs.read_documents"),
    );

    act(() => {
      hook.current.setDeploymentId("docs.default");
      hook.current.call({ names: ["README.md"] });
    });

    await waitFor(() => expect(hook.current.phase).toBe("result"));
    expect(mockedCallCapability).toHaveBeenCalledWith(writeExecutor, {
      qualifiedName: "local.docs.read_documents",
      payload: { names: ["README.md"] },
      deploymentId: "docs.default",
    } satisfies CapabilityCallRequest);
  });
});

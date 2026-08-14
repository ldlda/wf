import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ConnectionState } from "../../app/state.js";
import { useConsoleWorkspace } from "../context.js";
import {
  createAuthoringContractClient,
  type AuthoringContractClient,
} from "../domain/authoring-contract-client.js";
import type {
  AuthoringContractInventory,
  AuthoringPathOption,
} from "../domain/authoring-contract-models.js";
import type { ConsoleReadExecutor } from "../domain/read-executor.js";
import { useAuthoringContract } from "./useAuthoringContract.js";

vi.mock("../context.js", () => ({
  useConsoleWorkspace: vi.fn(),
}));

vi.mock("../domain/authoring-contract-client.js", async () => {
  const actual = await vi.importActual<typeof import("../domain/authoring-contract-client.js")>(
    "../domain/authoring-contract-client.js",
  );
  return { ...actual, createAuthoringContractClient: vi.fn() };
});

const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCreateAuthoringContractClient = vi.mocked(createAuthoringContractClient);

const connectedState = {
  phase: "connected",
  connectedTarget: "http://workflow.example/rpc",
} as ConnectionState;

const disconnectedState = {
  phase: "not_configured",
  connectedTarget: null,
} as ConnectionState;

const option: AuthoringPathOption = {
  path: "input.title",
  label: "Title",
  origin: "workflow_input",
  schema: { type: "string" },
  required: true,
  availability: "available",
  uses: ["step_input"],
};

const inventory = (revision: number, selectedStepId: string | null): AuthoringContractInventory => ({
  workspaceId: "draft-report",
  revision,
  selectedStepId,
  readableSources: [option],
  stepInputTargets: [],
  stepOutputSources: [],
  stateTargets: [],
  workflowOutputTargets: [],
  entrySteps: [],
  workflowOutcomes: ["ok"],
  warnings: [],
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const client = {
  inspect: vi.fn<AuthoringContractClient["inspect"]>(),
} satisfies AuthoringContractClient;

const readExecutor = {} as ConsoleReadExecutor;

beforeEach(() => {
  client.inspect.mockReset();
  mockedCreateAuthoringContractClient.mockReset();
  mockedCreateAuthoringContractClient.mockReturnValue(client);
  mockedUseConsoleWorkspace.mockReturnValue({
    connection: connectedState,
    connectedTarget: connectedState.connectedTarget,
    recordEvidence: vi.fn(),
    readExecutor,
    writeExecutor: null,
  });
});

describe("useAuthoringContract", () => {
  it("stays disconnected without a read executor", () => {
    mockedUseConsoleWorkspace.mockReturnValue({
      connection: disconnectedState,
      connectedTarget: null,
      recordEvidence: vi.fn(),
      readExecutor: null,
      writeExecutor: null,
    });

    const { result } = renderHook(() =>
      useAuthoringContract({ workspaceId: "draft-report", revision: 7, selectedStepId: null }),
    );

    expect(result.current.phase).toBe("disconnected");
    expect(client.inspect).not.toHaveBeenCalled();
  });

  it("loads the contract projection with a null selected step", async () => {
    client.inspect.mockResolvedValue(inventory(7, null));

    const { result } = renderHook(() =>
      useAuthoringContract({ workspaceId: "draft-report", revision: 7, selectedStepId: null }),
    );

    await waitFor(() => expect(result.current.phase).toBe("ready"));

    expect(client.inspect).toHaveBeenCalledWith({
      workspaceId: "draft-report",
      revision: 7,
      selectedStepId: null,
    });
    expect(result.current.inventory?.selectedStepId).toBeNull();
  });

  it("passes the executable step id and ignores a stale selection response", async () => {
    const first = deferred<AuthoringContractInventory>();
    const second = deferred<AuthoringContractInventory>();
    client.inspect.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);

    const { result, rerender } = renderHook(
      ({ selectedStepId }: { readonly selectedStepId: string | null }) =>
        useAuthoringContract({ workspaceId: "draft-report", revision: 7, selectedStepId }),
      { initialProps: { selectedStepId: "read" } },
    );

    await waitFor(() => expect(client.inspect).toHaveBeenCalledTimes(1));
    rerender({ selectedStepId: "render" });
    await waitFor(() => expect(client.inspect).toHaveBeenCalledTimes(2));

    first.resolve(inventory(7, "read"));
    second.resolve(inventory(7, "render"));

    await waitFor(() => expect(result.current.phase).toBe("ready"));
    expect(result.current.inventory?.selectedStepId).toBe("render");
    expect(client.inspect).toHaveBeenLastCalledWith({
      workspaceId: "draft-report",
      revision: 7,
      selectedStepId: "render",
    });
  });

  it("retains the last matching inventory when a refresh fails", async () => {
    client.inspect
      .mockResolvedValueOnce(inventory(7, "read"))
      .mockRejectedValueOnce(new Error("inspection failed"));

    const { result } = renderHook(() =>
      useAuthoringContract({ workspaceId: "draft-report", revision: 7, selectedStepId: "read" }),
    );
    await waitFor(() => expect(result.current.phase).toBe("ready"));

    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.phase).toBe("error"));

    expect(result.current.inventory?.selectedStepId).toBe("read");
    expect(result.current.message).toBe("inspection failed");
  });

  it("reloads when the revision changes and on manual refresh", async () => {
    client.inspect
      .mockResolvedValueOnce(inventory(7, "read"))
      .mockResolvedValueOnce(inventory(8, "read"))
      .mockResolvedValueOnce(inventory(8, "read"));

    const { result, rerender } = renderHook(
      ({ revision }: { readonly revision: number }) =>
        useAuthoringContract({ workspaceId: "draft-report", revision, selectedStepId: "read" }),
      { initialProps: { revision: 7 } },
    );
    await waitFor(() => expect(result.current.inventory?.revision).toBe(7));

    rerender({ revision: 8 });
    await waitFor(() => expect(result.current.inventory?.revision).toBe(8));
    act(() => result.current.refresh());
    await waitFor(() => expect(client.inspect).toHaveBeenCalledTimes(3));

    expect(client.inspect).toHaveBeenLastCalledWith({
      workspaceId: "draft-report",
      revision: 8,
      selectedStepId: "read",
    });
  });
});

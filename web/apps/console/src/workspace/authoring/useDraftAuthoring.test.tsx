import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useConsoleWorkspace } from "../context.js";
import type {
  DraftWorkspace,
  InputBinding,
  OutputBinding,
} from "../domain/draft-workspace-models.js";
import type { DraftAuthoringClient } from "../domain/draft-authoring-client.js";
import type { DraftWorkspaceClient } from "../domain/draft-workspace-client.js";
import type { ConsoleReadExecutor } from "../domain/read-executor.js";
import type { ConsoleWriteExecutor } from "../domain/write-executor.js";
import type { OperationName } from "../../connection/contracts.js";
import type { WorkbenchSelection } from "./authoring-graph.js";
import { createDraftAuthoringClient } from "../domain/draft-authoring-client.js";
import { createDraftWorkspaceClient } from "../domain/draft-workspace-client.js";
import type { CapabilitySetupPatch } from "./selected-step-dataflow.js";
import { useDraftAuthoring } from "./useDraftAuthoring.js";

vi.mock("../context.js", () => ({ useConsoleWorkspace: vi.fn() }));
vi.mock("../domain/draft-authoring-client.js", () => ({
  createDraftAuthoringClient: vi.fn(),
}));
vi.mock("../domain/draft-workspace-client.js", () => ({
  createDraftWorkspaceClient: vi.fn(),
}));

const mockedUseConsoleWorkspace = vi.mocked(useConsoleWorkspace);
const mockedCreateAuthoringClient = vi.mocked(createDraftAuthoringClient);
const mockedCreateWorkspaceClient = vi.mocked(createDraftWorkspaceClient);

const workspace = (overrides: Partial<DraftWorkspace> = {}): DraftWorkspace => ({
  workspaceId: "draft-report",
  revision: 3,
  title: "Report",
  status: "invalid",
  diagnostics: [],
  summary: {
    name: "report",
    start: null,
    stepCount: 0,
    routeCount: 0,
    steps: [],
  },
  draft: { steps: {}, routes: {} },
  ...overrides,
});

const capabilityInput = {
  stepId: "enrich",
  capabilityName: "demo.enrich",
  description: "Enrich report",
  retry: 1,
  timeoutSeconds: 30,
  inputBindings: [],
  bindOutputs: {},
};

const createEmpty = vi.fn<DraftAuthoringClient["createEmpty"]>();
const createFromCapability = vi.fn<DraftAuthoringClient["createFromCapability"]>();
const addCapabilityStep = vi.fn<DraftAuthoringClient["addCapabilityStep"]>();
const updateCapabilityStep = vi.fn<DraftAuthoringClient["updateCapabilityStep"]>();
const setStepInputBindings = vi.fn<DraftAuthoringClient["setStepInputBindings"]>();
const setStepOutputBindings = vi.fn<DraftAuthoringClient["setStepOutputBindings"]>();
const setRoute = vi.fn<DraftAuthoringClient["setRoute"]>();
const validate = vi.fn<DraftAuthoringClient["validate"]>();
const list = vi.fn<DraftWorkspaceClient["list"]>();
const load = vi.fn<DraftWorkspaceClient["load"]>();
const authoringClient = {
  createEmpty,
  createFromCapability,
  addCapabilityStep,
  updateCapabilityStep,
  setStepInputBindings,
  setStepOutputBindings,
  setRoute,
  validate,
} satisfies DraftAuthoringClient;
const workspaceClient = { list, load } satisfies DraftWorkspaceClient;
let contextValue: {
  connectedTarget: string | null;
  writeExecutor: ConsoleWriteExecutor | null;
  readExecutor: ConsoleReadExecutor | null;
};

const testRun = async function <T>(
  _operation: OperationName,
  _params: unknown,
  _decode: (value: unknown) => T,
): Promise<T> {
  throw new Error("test executor is not called");
};

const testExecutor: ConsoleReadExecutor & ConsoleWriteExecutor = { run: testRun };

beforeEach(() => {
  vi.clearAllMocks();
  contextValue = {
    connectedTarget: "server-a",
    writeExecutor: testExecutor,
    readExecutor: testExecutor,
  };
  mockedUseConsoleWorkspace.mockImplementation(() => ({
    ...contextValue,
    connection: {
      phase: "connected",
      draftTarget: "server-a",
      connectedTarget: "server-a",
      serverStatus: "ok",
      storeRoot: "/tmp",
      durationMs: 1,
      message: null,
      evidence: [],
    },
    recordEvidence: vi.fn(),
  }));
  mockedCreateAuthoringClient.mockReturnValue(authoringClient);
  mockedCreateWorkspaceClient.mockReturnValue(workspaceClient);
});

describe("useDraftAuthoring", () => {
  it("adds an unconnected capability without inventing route information", async () => {
    const initial = workspace();
    const canonical = workspace({
      revision: 4,
      draft: { steps: { enrich: { use: "demo.enrich" } }, routes: {} },
      summary: { ...initial.summary, stepCount: 1, steps: ["enrich"] },
    });
    authoringClient.addCapabilityStep.mockResolvedValue(canonical);
    const { result } = renderHook(() => useDraftAuthoring({ draft: initial }));

    await act(async () => result.current.addCapability(capabilityInput));

    expect(authoringClient.addCapabilityStep).toHaveBeenCalledWith({
      workspaceId: "draft-report",
      revision: 3,
      stepId: "enrich",
      capabilityName: "demo.enrich",
      description: "Enrich report",
      retry: 1,
      timeoutSeconds: 30,
      inputBindings: [],
      bindOutputs: {},
    });
    expect(result.current.draft).toBe(canonical);
    expect(result.current.selection).toEqual({ kind: "node", nodeId: "enrich" });
    expect(result.current.dirty).toBe(false);
  });

  it("lowers selected node and connector insertion context separately", async () => {
    const initial = workspace();
    authoringClient.addCapabilityStep.mockResolvedValue(workspace({ revision: 4 }));
    const { result, rerender } = renderHook(
      ({ selection }) => useDraftAuthoring({ draft: initial, initialSelection: selection }),
      { initialProps: { selection: { kind: "node", nodeId: "read" } as WorkbenchSelection } },
    );

    await act(async () => result.current.addCapability(capabilityInput));
    expect(authoringClient.addCapabilityStep.mock.calls.at(-1)?.[0]).not.toHaveProperty(
      "routeFromStep",
    );
    expect(authoringClient.addCapabilityStep.mock.calls.at(-1)?.[0]).not.toHaveProperty(
      "routeFromOutcome",
    );

    rerender({ selection: { kind: "edge", stepId: "read", outcome: "ok" } });
    await act(async () => result.current.addCapability({ ...capabilityInput, stepId: "publish" }));
    expect(authoringClient.addCapabilityStep).toHaveBeenLastCalledWith(
      expect.objectContaining({ routeFromStep: "read", routeFromOutcome: "ok" }),
    );
  });

  it("preserves selected connector context when capability selection follows", async () => {
    const initial = workspace();
    authoringClient.addCapabilityStep.mockResolvedValue(workspace({ revision: 4 }));
    const { result, rerender } = renderHook(
      ({ selection }) => useDraftAuthoring({ draft: initial, initialSelection: selection }),
      {
        initialProps: {
          selection: { kind: "edge", stepId: "read", outcome: "ok" } as WorkbenchSelection,
        },
      },
    );

    rerender({ selection: { kind: "capability", qualifiedName: "demo.enrich" } });
    await act(async () => result.current.addCapability(capabilityInput));

    expect(authoringClient.addCapabilityStep).toHaveBeenCalledWith(
      expect.objectContaining({ routeFromStep: "read", routeFromOutcome: "ok" }),
    );
  });

  it("updates capabilities, replaces routes, and validates against the current revision", async () => {
    const initial = workspace({ revision: 7 });
    authoringClient.updateCapabilityStep.mockResolvedValue(workspace({ revision: 8 }));
    authoringClient.setRoute.mockResolvedValue(workspace({ revision: 9 }));
    authoringClient.validate.mockResolvedValue(workspace({ revision: 9, status: "valid" }));
    const { result } = renderHook(() =>
      useDraftAuthoring({
        draft: initial,
        initialSelection: { kind: "node", nodeId: "read" },
      }),
    );

    await act(async () => result.current.updateCapability({ ...capabilityInput, stepId: "read" }));
    await act(async () =>
      result.current.setRoute({ stepId: "read", outcome: "ok", target: "publish" }),
    );
    await act(async () => result.current.validate());

    expect(authoringClient.updateCapabilityStep).toHaveBeenCalledWith(
      expect.objectContaining({ workspaceId: "draft-report", revision: 7, stepId: "read" }),
    );
    expect(authoringClient.setRoute).toHaveBeenCalledWith({
      workspaceId: "draft-report",
      revision: 8,
      stepId: "read",
      outcome: "ok",
      target: "publish",
    });
    expect(authoringClient.validate).toHaveBeenCalledWith("draft-report");
    expect(result.current.draft.status).toBe("valid");
  });

  it("targets the selected node when submitted metadata contains a different step id", async () => {
    const initial = workspace({
      draft: { steps: { read: { use: "demo.read" } }, routes: {} },
      summary: { name: "report", start: "read", stepCount: 1, routeCount: 0, steps: ["read"] },
    });
    updateCapabilityStep.mockResolvedValue(workspace({ revision: 4 }));
    const { result } = renderHook(() =>
      useDraftAuthoring({
        draft: initial,
        initialSelection: { kind: "node", nodeId: "read" },
      }),
    );

    await act(async () => result.current.updateCapability({ ...capabilityInput, stepId: "other" }));

    expect(updateCapabilityStep).toHaveBeenCalledWith(
      expect.objectContaining({ stepId: "read" }),
    );
  });

  it("preserves dirty form ownership on ordinary failures and revision conflicts", async () => {
    const initial = workspace();
    authoringClient.addCapabilityStep.mockRejectedValueOnce(new Error("server unavailable"));
    const { result } = renderHook(() =>
      useDraftAuthoring({
        draft: initial,
        initialSelection: { kind: "capability", qualifiedName: "demo.enrich" },
      }),
    );

    await act(async () => result.current.addCapability(capabilityInput));
    expect(result.current.phase).toBe("error");
    expect(result.current.draft).toBe(initial);
    expect(result.current.dirty).toBe(true);

    const conflict = workspace({
      revision: 4,
      status: "conflict",
      diagnostics: [
        {
          code: "revision_conflict",
          path: "revision",
          message: "Draft changed on the server.",
          stepId: null,
          repairHint: null,
          details: {},
        },
      ],
    });
    authoringClient.addCapabilityStep.mockResolvedValue(conflict);
    await act(async () => result.current.addCapability(capabilityInput));
    expect(result.current.phase).toBe("conflict");
    expect(result.current.draft).toBe(conflict);
    expect(result.current.dirty).toBe(true);
    expect(result.current.selection).toEqual({
      kind: "capability",
      qualifiedName: "demo.enrich",
    });
  });

  it("preserves an update form when a conflict response has no draft", async () => {
    const initial = workspace({
      draft: { steps: { read: { use: "demo.read" } }, routes: {} },
    });
    const conflict = workspace({
      revision: 4,
      status: "conflict",
      draft: null,
      summary: { ...initial.summary, steps: [] },
    });
    authoringClient.updateCapabilityStep.mockResolvedValue(conflict);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "read" },
    }));
    const input = { ...capabilityInput, stepId: "read", capabilityName: "demo.read" };

    await act(async () => result.current.updateCapability(input));

    expect(result.current.draft).toBe(conflict);
    expect(result.current.selection).toEqual({ kind: "node", nodeId: "read" });
    expect(result.current.preservedCapabilityForm).toEqual({ kind: "update", input });
  });

  it("does not send different writes or validation concurrently for one revision", async () => {
    const initial = workspace({ revision: 6 });
    let resolveAdd: ((value: DraftWorkspace) => void) | undefined;
    authoringClient.addCapabilityStep.mockReturnValueOnce(
      new Promise<DraftWorkspace>((resolve) => { resolveAdd = resolve; }),
    );
    const { result } = renderHook(() => useDraftAuthoring({ draft: initial }));

    let first: Promise<void> | undefined;
    act(() => { first = result.current.addCapability(capabilityInput); });
    const second = result.current.addCapability({ ...capabilityInput, stepId: "publish" });
    const validation = result.current.validate();

    await expect(second).rejects.toThrow("Another draft authoring request is in progress.");
    await expect(validation).rejects.toThrow("Another draft authoring request is in progress.");
    expect(authoringClient.addCapabilityStep).toHaveBeenCalledTimes(1);
    expect(authoringClient.validate).not.toHaveBeenCalled();

    resolveAdd?.(workspace({ revision: 7 }));
    await act(async () => first);
  });

  it("coalesces duplicate validation requests for the loaded revision", async () => {
    const initial = workspace({ revision: 8 });
    let resolveValidation: ((value: DraftWorkspace) => void) | undefined;
    authoringClient.validate.mockReturnValueOnce(
      new Promise<DraftWorkspace>((resolve) => { resolveValidation = resolve; }),
    );
    const { result } = renderHook(() => useDraftAuthoring({ draft: initial }));

    let first: Promise<void> | undefined;
    let second: Promise<void> | undefined;
    act(() => {
      first = result.current.validate();
      second = result.current.validate();
    });

    expect(first).toBe(second);
    expect(authoringClient.validate).toHaveBeenCalledTimes(1);
    resolveValidation?.(workspace({ revision: 8, status: "valid" }));
    await act(async () => first);
  });

  it("rejects mutation, validation, and reload responses for another workspace", async () => {
    const initial = workspace();
    const wrongWorkspace = workspace({ workspaceId: "other-workspace", revision: 99 });
    authoringClient.addCapabilityStep.mockResolvedValueOnce(wrongWorkspace);
    authoringClient.validate.mockResolvedValueOnce(wrongWorkspace);
    workspaceClient.load.mockResolvedValueOnce(wrongWorkspace);
    const { result } = renderHook(() => useDraftAuthoring({ draft: initial }));

    await act(async () => result.current.addCapability(capabilityInput));
    expect(result.current.draft).toBe(initial);
    await act(async () => result.current.validate());
    expect(result.current.draft).toBe(initial);
    await act(async () => result.current.reload());
    expect(result.current.draft).toBe(initial);
  });

  it("reapplies the current preserved form value after a conflict", async () => {
    const initial = workspace();
    const conflict = workspace({ revision: 4, status: "conflict" });
    authoringClient.addCapabilityStep
      .mockResolvedValueOnce(conflict)
      .mockResolvedValueOnce(workspace({ revision: 5 }));
    const { result } = renderHook(() => useDraftAuthoring({ draft: initial }));

    await act(async () => result.current.addCapability(capabilityInput));
    act(() => result.current.rememberCapabilityForm("add", { ...capabilityInput, description: "edited after conflict" }));
    await act(async () => result.current.reapply());

    expect(authoringClient.addCapabilityStep).toHaveBeenLastCalledWith(
      expect.objectContaining({ description: "edited after conflict" }),
    );
  });

  it("reapplies a conflicted update to its original node after selection changes", async () => {
    const initial = workspace({
      draft: {
        steps: {
          read: { use: "demo.read" },
          publish: { use: "demo.publish" },
        },
        routes: {},
      },
    });
    const conflict = workspace({ revision: 4, status: "conflict", draft: null });
    authoringClient.updateCapabilityStep
      .mockResolvedValueOnce(conflict)
      .mockResolvedValueOnce(workspace({ revision: 5 }));
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "read" },
    }));

    await act(async () => result.current.updateCapability({
      ...capabilityInput,
      stepId: "read",
      capabilityName: "demo.read",
    }));
    act(() => result.current.select({ kind: "node", nodeId: "publish" }));
    await act(async () => result.current.reapply());

    expect(authoringClient.updateCapabilityStep).toHaveBeenLastCalledWith(
      expect.objectContaining({ stepId: "read" }),
    );
  });

  it("reloads explicitly and coalesces duplicate submissions", async () => {
    const initial = workspace();
    const reloaded = workspace({ revision: 10, status: "valid" });
    let resolveAdd: ((value: DraftWorkspace) => void) | undefined;
    authoringClient.addCapabilityStep.mockReturnValue(
      new Promise<DraftWorkspace>((resolve) => {
        resolveAdd = resolve;
      }),
    );
    workspaceClient.load.mockResolvedValue(reloaded);
    const { result } = renderHook(() => useDraftAuthoring({ draft: initial }));

    let first: Promise<void> | undefined;
    let second: Promise<void> | undefined;
    act(() => {
      first = result.current.addCapability(capabilityInput);
      second = result.current.addCapability(capabilityInput);
    });
    expect(first).toBe(second);
    expect(authoringClient.addCapabilityStep).toHaveBeenCalledTimes(1);

    resolveAdd?.(workspace({ revision: 11 }));
    await act(async () => first);
    await act(async () => result.current.reload());
    expect(workspaceClient.load).toHaveBeenCalledWith("draft-report");
    expect(result.current.draft).toBe(reloaded);
    expect(result.current.dirty).toBe(false);
  });

  it("rejects a mutation response after the connection target changes", async () => {
    const initial = workspace();
    let resolveAdd: ((value: DraftWorkspace) => void) | undefined;
    authoringClient.addCapabilityStep.mockReturnValue(
      new Promise<DraftWorkspace>((resolve) => {
        resolveAdd = resolve;
      }),
    );
    const { result, rerender } = renderHook(() => useDraftAuthoring({ draft: initial }));

    act(() => {
      void result.current.addCapability(capabilityInput);
    });
    contextValue = { ...contextValue, connectedTarget: "server-b" };
    rerender();
    resolveAdd?.(workspace({ revision: 12 }));
    await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));

    expect(result.current.draft).toBe(initial);
    expect(result.current.dirty).toBe(true);
  });

  it("submits selected-step inputs against the selected node and current revision", async () => {
    const initial = workspace({ revision: 7 });
    const canonical = workspace({ revision: 8 });
    const bindings = [
      { path: "input.title", target: "title" },
      { target: "separator", value: null },
    ] satisfies ReadonlyArray<InputBinding>;
    setStepInputBindings.mockResolvedValue(canonical);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));

    await act(async () => result.current.setStepInputs(bindings));

    expect(setStepInputBindings).toHaveBeenCalledWith({
      workspaceId: "draft-report",
      revision: 7,
      stepId: "render",
      bindings,
    });
    expect(result.current.draft).toBe(canonical);
  });

  it("submits ordered output bindings and commits the returned draft", async () => {
    const initial = workspace({ revision: 4 });
    const canonical = workspace({ revision: 5 });
    const bindings = [
      { source: "text", target: "state.report" },
      { source: "text", target: "state.audit.latest" },
    ] satisfies ReadonlyArray<OutputBinding>;
    setStepOutputBindings.mockResolvedValue(canonical);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));

    await act(async () => result.current.setStepOutputs(bindings));

    expect(setStepOutputBindings).toHaveBeenCalledWith({
      workspaceId: "draft-report",
      revision: 4,
      stepId: "render",
      bindings,
    });
    expect(result.current.draft).toBe(canonical);
  });

  it("sends only present setup fields, including zero and explicit null", async () => {
    const initial = workspace({ revision: 7 });
    updateCapabilityStep
      .mockResolvedValueOnce(workspace({ revision: 8 }))
      .mockResolvedValueOnce(workspace({ revision: 9 }));
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));

    const retryPatch = { retry: 0 } satisfies CapabilitySetupPatch;
    await act(async () => result.current.updateSetup(retryPatch));
    await act(async () => result.current.updateSetup({ timeoutSeconds: null }));

    expect(updateCapabilityStep).toHaveBeenNthCalledWith(1, {
      workspaceId: "draft-report",
      revision: 7,
      stepId: "render",
      update: { retry: 0 },
    });
    expect(updateCapabilityStep).toHaveBeenNthCalledWith(2, {
      workspaceId: "draft-report",
      revision: 8,
      stepId: "render",
      update: { timeoutSeconds: null },
    });
  });

  it("coalesces duplicate selected-step mutations and rejects a different pending mutation", async () => {
    const initial = workspace({ revision: 6 });
    let resolveInputs: ((value: DraftWorkspace) => void) | undefined;
    setStepInputBindings.mockReturnValueOnce(
      new Promise<DraftWorkspace>((resolve) => { resolveInputs = resolve; }),
    );
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));
    const bindings = [{ path: "input.title", target: "title" }] satisfies ReadonlyArray<InputBinding>;

    let first: Promise<void> | undefined;
    let duplicate: Promise<void> | undefined;
    act(() => {
      first = result.current.setStepInputs(bindings);
      duplicate = result.current.setStepInputs(bindings);
    });
    const different = result.current.setStepOutputs([
      { source: "text", target: "state.report" },
    ] satisfies ReadonlyArray<OutputBinding>);

    expect(first).toBe(duplicate);
    await expect(different).rejects.toThrow("Another draft authoring request is in progress.");
    expect(setStepInputBindings).toHaveBeenCalledTimes(1);
    expect(setStepOutputBindings).not.toHaveBeenCalled();

    resolveInputs?.(workspace({ revision: 7 }));
    await act(async () => first);
  });

  it("ignores a selected-step response after the selection target becomes stale", async () => {
    const initial = workspace({ revision: 7 });
    let resolveInputs: ((value: DraftWorkspace) => void) | undefined;
    setStepInputBindings.mockReturnValueOnce(
      new Promise<DraftWorkspace>((resolve) => { resolveInputs = resolve; }),
    );
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));
    const request = result.current.setStepInputs([
      { path: "input.title", target: "title" },
    ]);

    act(() => result.current.select({ kind: "node", nodeId: "publish" }));
    resolveInputs?.(workspace({ revision: 8 }));
    await act(async () => request);

    expect(result.current.draft).toBe(initial);
    expect(result.current.selection).toEqual({ kind: "node", nodeId: "publish" });
  });

  it("reapplies the exact input submission to its original step after reload", async () => {
    const initial = workspace({ revision: 7 });
    const conflict = workspace({ revision: 7, status: "conflict" });
    const reloaded = workspace({ revision: 8, status: "invalid" });
    const canonical = workspace({ revision: 9 });
    const bindings = [
      { path: "input.items", target: "items" },
      { target: "separator", value: null },
      { path: "state.fallback", target: "fallback" },
    ] satisfies ReadonlyArray<InputBinding>;
    setStepInputBindings.mockResolvedValueOnce(conflict).mockResolvedValueOnce(canonical);
    load.mockResolvedValue(reloaded);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));

    await act(async () => result.current.setStepInputs(bindings));
    act(() => result.current.select({ kind: "node", nodeId: "publish" }));
    await act(async () => result.current.reload());
    await act(async () => result.current.reapply());

    expect(setStepInputBindings).toHaveBeenLastCalledWith({
      workspaceId: "draft-report",
      revision: 8,
      stepId: "render",
      bindings,
    });
    expect(result.current.draft).toBe(canonical);
  });

  it("reapplies the exact output submission to its original step after reload", async () => {
    const initial = workspace({ revision: 7 });
    const conflict = workspace({ revision: 7, status: "conflict" });
    const reloaded = workspace({ revision: 8, status: "invalid" });
    const canonical = workspace({ revision: 9 });
    const bindings = [
      { source: "text", target: "state.report" },
      { source: "text", target: "state.audit.latest" },
    ] satisfies ReadonlyArray<OutputBinding>;
    setStepOutputBindings.mockResolvedValueOnce(conflict).mockResolvedValueOnce(canonical);
    load.mockResolvedValue(reloaded);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));

    await act(async () => result.current.setStepOutputs(bindings));
    act(() => result.current.select({ kind: "node", nodeId: "publish" }));
    await act(async () => result.current.reload());
    await act(async () => result.current.reapply());

    expect(setStepOutputBindings).toHaveBeenLastCalledWith({
      workspaceId: "draft-report",
      revision: 8,
      stepId: "render",
      bindings,
    });
    expect(result.current.draft).toBe(canonical);
  });

  it("reapplies the exact setup patch to its original step after reload", async () => {
    const initial = workspace({ revision: 7 });
    const conflict = workspace({ revision: 7, status: "conflict" });
    const reloaded = workspace({ revision: 8, status: "invalid" });
    const canonical = workspace({ revision: 9 });
    updateCapabilityStep.mockResolvedValueOnce(conflict).mockResolvedValueOnce(canonical);
    load.mockResolvedValue(reloaded);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));
    const patch = { retry: 0 } satisfies CapabilitySetupPatch;

    await act(async () => result.current.updateSetup(patch));
    act(() => result.current.select({ kind: "node", nodeId: "publish" }));
    await act(async () => result.current.reload());
    await act(async () => result.current.reapply());

    expect(updateCapabilityStep).toHaveBeenLastCalledWith({
      workspaceId: "draft-report",
      revision: 8,
      stepId: "render",
      update: { retry: 0 },
    });
    expect(result.current.draft).toBe(canonical);
  });

  it("reapplies an immutable input snapshot after caller-owned values mutate", async () => {
    const initial = workspace({ revision: 7 });
    const conflict = workspace({ revision: 7, status: "conflict" });
    const reloaded = workspace({ revision: 8, status: "invalid" });
    const canonical = workspace({ revision: 9 });
    const pathBinding = {
      path: { root: "state" as const, parts: ["fallback", "value"] },
      target: { root: "local" as const, parts: ["fallback"] },
    } satisfies InputBinding;
    const literalBinding = {
      target: { root: "local" as const, parts: ["options"] },
      value: { nested: { items: [{ enabled: true }] } },
    } satisfies InputBinding;
    const bindings: InputBinding[] = [pathBinding, literalBinding];
    const expectedBindings: ReadonlyArray<InputBinding> = [
      {
        path: { root: "state", parts: ["fallback", "value"] },
        target: { root: "local", parts: ["fallback"] },
      },
      {
        target: { root: "local", parts: ["options"] },
        value: { nested: { items: [{ enabled: true }] } },
      },
    ];
    setStepInputBindings.mockResolvedValueOnce(conflict).mockResolvedValueOnce(canonical);
    load.mockResolvedValue(reloaded);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));

    await act(async () => result.current.setStepInputs(bindings));
    pathBinding.path.parts[0] = "context";
    pathBinding.target.parts[0] = "mutated-target";
    Object.assign(literalBinding, { target: "mutated-target" });
    const firstItem = literalBinding.value.nested.items[0];
    if (firstItem !== undefined) firstItem.enabled = false;
    bindings.push({ target: "added", value: true });
    act(() => result.current.select({ kind: "node", nodeId: "publish" }));
    await act(async () => result.current.reload());
    await act(async () => result.current.reapply());

    expect(setStepInputBindings).toHaveBeenLastCalledWith({
      workspaceId: "draft-report",
      revision: 8,
      stepId: "render",
      bindings: expectedBindings,
    });
  });

  it("reapplies an immutable output snapshot after caller-owned values mutate", async () => {
    const initial = workspace({ revision: 7 });
    const conflict = workspace({ revision: 7, status: "conflict" });
    const reloaded = workspace({ revision: 8, status: "invalid" });
    const canonical = workspace({ revision: 9 });
    const firstBinding = {
      source: { root: "local" as const, parts: ["text"] },
      target: { root: "state" as const, parts: ["report"] },
    } satisfies OutputBinding;
    const secondBinding = {
      source: { root: "local" as const, parts: ["text"] },
      target: "state.audit.latest",
    } satisfies OutputBinding;
    const bindings: OutputBinding[] = [firstBinding, secondBinding];
    const expectedBindings: ReadonlyArray<OutputBinding> = [
      {
        source: { root: "local", parts: ["text"] },
        target: { root: "state", parts: ["report"] },
      },
      { source: { root: "local", parts: ["text"] }, target: "state.audit.latest" },
    ];
    setStepOutputBindings.mockResolvedValueOnce(conflict).mockResolvedValueOnce(canonical);
    load.mockResolvedValue(reloaded);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));

    await act(async () => result.current.setStepOutputs(bindings));
    firstBinding.source.parts[0] = "mutated-source";
    firstBinding.target.parts[0] = "mutated-target";
    Object.assign(secondBinding, { source: "mutated-source", target: "mutated-target" });
    bindings.push({ source: "added", target: "state.added" });
    act(() => result.current.select({ kind: "node", nodeId: "publish" }));
    await act(async () => result.current.reload());
    await act(async () => result.current.reapply());

    expect(setStepOutputBindings).toHaveBeenLastCalledWith({
      workspaceId: "draft-report",
      revision: 8,
      stepId: "render",
      bindings: expectedBindings,
    });
  });

  it("reapplies an immutable setup patch after the caller mutates it", async () => {
    const initial = workspace({ revision: 7 });
    const conflict = workspace({ revision: 7, status: "conflict" });
    const reloaded = workspace({ revision: 8, status: "invalid" });
    const canonical = workspace({ revision: 9 });
    const patch = { description: "Original", retry: 0, timeoutSeconds: null } satisfies CapabilitySetupPatch;
    updateCapabilityStep.mockResolvedValueOnce(conflict).mockResolvedValueOnce(canonical);
    load.mockResolvedValue(reloaded);
    const { result } = renderHook(() => useDraftAuthoring({
      draft: initial,
      initialSelection: { kind: "node", nodeId: "render" },
    }));

    await act(async () => result.current.updateSetup(patch));
    Object.assign(patch, { description: "Mutated", retry: 4, timeoutSeconds: 30 });
    act(() => result.current.select({ kind: "node", nodeId: "publish" }));
    await act(async () => result.current.reload());
    await act(async () => result.current.reapply());

    expect(updateCapabilityStep).toHaveBeenLastCalledWith({
      workspaceId: "draft-report",
      revision: 8,
      stepId: "render",
      update: { description: "Original", retry: 0, timeoutSeconds: null },
    });
  });
});

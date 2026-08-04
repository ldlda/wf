import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ArtifactClient,
  DeploymentClient,
  LifecycleClients,
  RunClient,
} from "../workspace/domain/lifecycle-clients.js";
import { useLifecycleExplorer } from "./useLifecycleExplorer.js";
import type { LifecycleState } from "./state.js";
import type {
  ArtifactDetail,
  ArtifactList,
  DeploymentDetail,
  DeploymentList,
  DeploymentValidation,
  RunDetail,
  RunList,
  TracePage,
} from "./models.js";

const artifactList: ArtifactList = { items: [], total: 0, nextCursor: null };
const deploymentList: DeploymentList = { items: [] };
const runList: RunList = { items: [], total: 0, nextCursor: null };
const artifactDetail = {
  artifactId: "report",
  version: 2,
  title: "Report",
  kind: "workflow",
  description: null,
  outcomes: ["ok"],
  plan: { nodes: [], edges: [] },
  requiredCapabilities: [],
  workflowDependencies: {},
  createdFromCatalogVersion: null,
} satisfies ArtifactDetail;
const deploymentDetail = {
  id: "report.default",
  artifactId: "report",
  artifactVersion: 2,
  bindings: [],
  driftPolicy: "block",
} satisfies DeploymentDetail;
const deploymentValidation = {
  deploymentId: "report.default",
  artifactId: "report",
  artifactVersion: 2,
  status: "runnable",
  diagnostics: [],
  nextActions: {
    canContinue: true,
    canSaveNow: null,
    recommendedNextTool: null,
    reason: "ready",
    patchExamples: [],
    warnings: [],
  },
} satisfies DeploymentValidation;
const runDetail = {
  runId: "run_123",
  deploymentId: "report.default",
  artifactId: "report",
  artifactVersion: 2,
  status: "completed",
  resumeReadiness: "not_applicable",
  interrupt: null,
  outcome: "ok",
  error: null,
  output: {},
  diagnostics: [],
  traceCount: 0,
  nextActions: {
    canContinue: false,
    canSaveNow: null,
    recommendedNextTool: null,
    reason: "done",
    patchExamples: [],
    warnings: [],
  },
} satisfies RunDetail;

const makeClients = (overrides: Partial<{
  artifacts: Partial<ArtifactClient>;
  deployments: Partial<DeploymentClient>;
  runs: Partial<RunClient>;
}> = {}): LifecycleClients => ({
  artifacts: {
    list: vi.fn().mockResolvedValue(artifactList),
    inspect: vi.fn().mockResolvedValue(artifactDetail),
    ...overrides.artifacts,
  },
  deployments: {
    list: vi.fn().mockResolvedValue(deploymentList),
    inspect: vi.fn().mockResolvedValue(deploymentDetail),
    validate: vi.fn().mockResolvedValue(deploymentValidation),
    ...overrides.deployments,
  },
  runs: {
    list: vi.fn().mockResolvedValue(runList),
    inspect: vi.fn().mockResolvedValue(runDetail),
    trace: vi.fn().mockResolvedValue({
      frames: [],
      traceStart: 0,
      traceLimit: 50,
      traceTruncated: false,
    }),
    ...overrides.runs,
  },
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

beforeEach(() => vi.restoreAllMocks());

describe("useLifecycleExplorer", () => {
  it("loads all lifecycle collections through the Task 3 clients", async () => {
    const clients = makeClients();
    renderHook(() => useLifecycleExplorer(clients));

    await waitFor(() => {
      expect(clients.artifacts.list).toHaveBeenCalledWith({ limit: 50 });
      expect(clients.deployments.list).toHaveBeenCalledWith();
      expect(clients.runs.list).toHaveBeenCalledWith({ limit: 50 });
    });
  });

  it("uses domain methods for artifact, deployment, and run inspection", async () => {
    const clients = makeClients();
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => {
      result.current.selectArtifact("report@2");
      result.current.selectDeployment("report.default");
      result.current.selectRun("run_123");
    });

    await waitFor(() => {
      expect(clients.artifacts.inspect).toHaveBeenCalledWith("report", 2);
      expect(clients.deployments.inspect).toHaveBeenCalledWith("report.default");
      expect(clients.deployments.validate).toHaveBeenCalledWith("report.default");
      expect(clients.runs.inspect).toHaveBeenCalledWith("run_123");
    });
  });

  it("keeps a late response from the previous client generation out of state", async () => {
    let releaseFirst!: (value: ArtifactList) => void;
    const firstList = new Promise<ArtifactList>((resolve) => {
      releaseFirst = resolve;
    });
    const first = makeClients({ artifacts: { list: vi.fn().mockReturnValue(firstList) } });
    const second = makeClients({
      artifacts: {
        list: vi.fn().mockResolvedValue({
          items: [
            {
              key: "new@1",
              artifactId: "new",
              version: 1,
              kind: "workflow",
              displayName: "New",
              description: null,
              outcomes: [],
              requiredSources: [],
              diagnosticCount: 0,
            },
          ],
          total: 1,
          nextCursor: null,
        }),
      },
    });
    const { result, rerender } = renderHook(
      ({ clients: currentClients }) => useLifecycleExplorer(currentClients),
      { initialProps: { clients: first } },
    );

    rerender({ clients: second });
    await waitFor(() => expect(result.current.state.artifactList.phase).toBe("loaded"));
    releaseFirst(artifactList);
    await act(async () => await firstList);

    expect(result.current.state.artifactList).toMatchObject({
      phase: "loaded",
      value: { items: [{ key: "new@1" }] },
    });
  });

  it("fails closed immediately when the lifecycle client bundle changes", async () => {
    const oldArtifactList: ArtifactList = {
      items: [{
        key: "old@1",
        artifactId: "old",
        version: 1,
        kind: "workflow",
        displayName: "Old",
        description: null,
        outcomes: [],
        requiredSources: [],
        diagnosticCount: 0,
      }],
      total: 1,
      nextCursor: null,
    };
    const oldDeploymentList: DeploymentList = {
      items: [{
        id: "old.default",
        artifactId: "old",
        artifactVersion: 1,
        bindingCount: 0,
        driftPolicy: "block",
      }],
    };
    const oldRunList: RunList = {
      items: [{
        runId: "old-run",
        deploymentId: "old.default",
        artifactId: "old",
        artifactVersion: 1,
        status: "completed",
        resumeReadiness: "not_applicable",
        diagnosticCount: 0,
      }],
      total: 1,
      nextCursor: null,
    };
    const first = makeClients({
      artifacts: { list: vi.fn().mockResolvedValue(oldArtifactList) },
      deployments: { list: vi.fn().mockResolvedValue(oldDeploymentList) },
      runs: { list: vi.fn().mockResolvedValue(oldRunList) },
    });
    const never = <T,>(): Promise<T> => new Promise<T>(() => undefined);
    const second = makeClients({
      artifacts: { list: vi.fn().mockImplementation(() => never<ArtifactList>()) },
      deployments: { list: vi.fn().mockImplementation(() => never<DeploymentList>()) },
      runs: { list: vi.fn().mockImplementation(() => never<RunList>()) },
    });
    const renders: LifecycleState[] = [];
    const { result, rerender } = renderHook(
      ({ clients }: { clients: LifecycleClients | null }) => {
        const current = useLifecycleExplorer(clients);
        renders.push(current.state);
        return current;
      },
      { initialProps: { clients: first } },
    );

    await waitFor(() => expect(result.current.state.artifactList.phase).toBe("loaded"));
    act(() => result.current.selectArtifact("report@2"));
    await waitFor(() => expect(result.current.state.artifactDetail).not.toBeNull());
    const renderCountBeforeClientChange = renders.length;
    rerender({ clients: second });

    const transitionState = renders[renderCountBeforeClientChange];
    expect(transitionState?.artifactList).toEqual({ phase: "idle" });
    expect(transitionState?.deploymentList).toEqual({ phase: "idle" });
    expect(transitionState?.runList).toEqual({ phase: "idle" });
    expect(transitionState?.artifactDetail).toBeNull();
    expect(transitionState?.deploymentDetail).toBeNull();
    expect(transitionState?.deploymentValidation).toBeNull();
    expect(transitionState?.runDetail).toBeNull();
    expect(transitionState?.trace).toBeNull();
  });

  it("rejects a late artifact inspect after the URL-owned id changes", async () => {
    let releaseFirst!: (value: ArtifactDetail) => void;
    const firstInspect = new Promise<ArtifactDetail>((resolve) => {
      releaseFirst = resolve;
    });
    const inspect = vi.fn((_: string, version: number) =>
      version === 1 ? firstInspect : Promise.resolve(artifactDetail),
    );
    const clients = makeClients({ artifacts: { inspect } });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => result.current.selectArtifact("report@1"));
    act(() => result.current.selectArtifact("report@2"));
    await waitFor(() => expect(result.current.state.artifactDetail?.version).toBe(2));

    releaseFirst({ ...artifactDetail, version: 1 });
    await act(async () => await firstInspect);

    expect(result.current.state.selectedArtifactId).toBe("report@2");
    expect(result.current.state.artifactDetail?.version).toBe(2);
  });

  it("rejects a late artifact detail after a null selection", async () => {
    const detail = deferred<ArtifactDetail>();
    const clients = makeClients({
      artifacts: { inspect: vi.fn().mockReturnValue(detail.promise) },
    });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => result.current.selectArtifact("report@2"));
    act(() => result.current.selectArtifact(null));
    detail.resolve(artifactDetail);
    await act(async () => await detail.promise);

    expect(result.current.state.selectedArtifactId).toBeNull();
    expect(result.current.state.artifactDetail).toBeNull();
  });

  it("rejects a late artifact detail after a cross-kind selection", async () => {
    const detail = deferred<ArtifactDetail>();
    const clients = makeClients({
      artifacts: { inspect: vi.fn().mockReturnValue(detail.promise) },
    });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => result.current.selectArtifact("report@2"));
    act(() => result.current.selectDeployment("report.default"));
    detail.resolve(artifactDetail);
    await act(async () => await detail.promise);

    expect(result.current.state.artifactDetail).toBeNull();
  });

  it("rejects late deployment validation after a cross-kind selection", async () => {
    const validation = deferred<DeploymentValidation>();
    const clients = makeClients({
      deployments: { validate: vi.fn().mockReturnValue(validation.promise) },
    });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => result.current.selectDeployment("report.default"));
    act(() => result.current.selectArtifact(null));
    validation.resolve(deploymentValidation);
    await act(async () => await validation.promise);

    expect(result.current.state.deploymentValidation).toBeNull();
  });

  it("rejects a late deployment detail after a null selection", async () => {
    const detail = deferred<DeploymentDetail>();
    const clients = makeClients({
      deployments: { inspect: vi.fn().mockReturnValue(detail.promise) },
    });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => result.current.selectDeployment("report.default"));
    act(() => result.current.selectDeployment(null));
    detail.resolve(deploymentDetail);
    await act(async () => await detail.promise);

    expect(result.current.state.selectedDeploymentId).toBeNull();
    expect(result.current.state.deploymentDetail).toBeNull();
  });

  it("rejects a late run detail after a cross-kind selection", async () => {
    const detail = deferred<RunDetail>();
    const clients = makeClients({
      runs: { inspect: vi.fn().mockReturnValue(detail.promise) },
    });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => result.current.selectRun("run_123"));
    act(() => result.current.selectArtifact(null));
    detail.resolve(runDetail);
    await act(async () => await detail.promise);

    expect(result.current.state.selectedRunId).toBeNull();
    expect(result.current.state.runDetail).toBeNull();
  });

  it("rejects a late run trace after a null selection", async () => {
    const trace = deferred<TracePage>();
    const clients = makeClients({
      runs: {
        inspect: vi.fn().mockResolvedValue({ ...runDetail, traceCount: 1 }),
        trace: vi.fn().mockReturnValue(trace.promise),
      },
    });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => result.current.selectRun("run_123"));
    await waitFor(() => expect(clients.runs.trace).toHaveBeenCalledWith("run_123", 0, 50));
    act(() => result.current.selectDeployment(null));
    trace.resolve({ frames: [], traceStart: 0, traceLimit: 50, traceTruncated: false });
    await act(async () => await trace.promise);

    expect(result.current.state.selectedRunId).toBeNull();
    expect(result.current.state.trace).toBeNull();
  });

  it("rejects a late run trace after a cross-kind selection", async () => {
    const trace = deferred<TracePage>();
    const clients = makeClients({
      runs: {
        inspect: vi.fn().mockResolvedValue({ ...runDetail, traceCount: 1 }),
        trace: vi.fn().mockReturnValue(trace.promise),
      },
    });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => result.current.selectRun("run_123"));
    await waitFor(() => expect(clients.runs.trace).toHaveBeenCalledWith("run_123", 0, 50));
    act(() => result.current.selectArtifact(null));
    trace.resolve({ frames: [], traceStart: 0, traceLimit: 50, traceTruncated: false });
    await act(async () => await trace.promise);

    expect(result.current.state.trace).toBeNull();
  });

  it("finishes every collection load when a direct detail selection starts first", async () => {
    const artifacts = deferred<ArtifactList>();
    const deployments = deferred<DeploymentList>();
    const runs = deferred<RunList>();
    const clients = makeClients({
      artifacts: { list: vi.fn().mockReturnValue(artifacts.promise) },
      deployments: { list: vi.fn().mockReturnValue(deployments.promise) },
      runs: { list: vi.fn().mockReturnValue(runs.promise) },
    });
    const { result } = renderHook(() => useLifecycleExplorer(clients));

    act(() => {
      result.current.selectArtifact("report@2");
      result.current.selectDeployment("report.default");
      result.current.selectRun("run_123");
    });
    artifacts.resolve(artifactList);
    deployments.resolve(deploymentList);
    runs.resolve(runList);
    await act(async () => await Promise.all([
      artifacts.promise,
      deployments.promise,
      runs.promise,
    ]));

    expect(result.current.state.artifactList.phase).toBe("loaded");
    expect(result.current.state.deploymentList.phase).toBe("loaded");
    expect(result.current.state.runList.phase).toBe("loaded");
  });

  it("clears lifecycle state when the client bundle is disconnected", async () => {
    const clients = makeClients();
    const { result, rerender } = renderHook(
      ({ currentClients }) => useLifecycleExplorer(currentClients),
      { initialProps: { currentClients: clients as LifecycleClients | null } },
    );

    await waitFor(() => expect(result.current.state.artifactList.phase).toBe("loaded"));
    rerender({ currentClients: null });

    expect(result.current.state).toEqual({
      artifactList: { phase: "idle" },
      deploymentList: { phase: "idle" },
      runList: { phase: "idle" },
      selectedArtifactId: null,
      artifactDetail: null,
      selectedDeploymentId: null,
      deploymentDetail: null,
      deploymentValidation: null,
      selectedRunId: null,
      runDetail: null,
      trace: null,
      errors: [],
    });
  });
});

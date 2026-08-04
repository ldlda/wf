import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  ArtifactClient,
  DeploymentClient,
  LifecycleClients,
  RunClient,
} from "../workspace/domain/lifecycle-clients.js";
import { useLifecycleExplorer } from "./useLifecycleExplorer.js";
import type {
  ArtifactDetail,
  ArtifactList,
  DeploymentDetail,
  DeploymentList,
  DeploymentValidation,
  RunDetail,
  RunList,
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

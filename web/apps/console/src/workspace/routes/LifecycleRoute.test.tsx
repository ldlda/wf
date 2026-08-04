import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LifecycleExplorerController } from "../../lifecycle/useLifecycleExplorer.js";
import type { LifecycleState } from "../../lifecycle/state.js";
import { LifecycleRoute } from "./LifecycleRoute.js";

const { mockCreateLifecycleClients, mockUseLifecycleExplorer } = vi.hoisted(() => ({
  mockCreateLifecycleClients: vi.fn(),
  mockUseLifecycleExplorer: vi.fn(),
}));

vi.mock("../context.js", () => ({
  useConsoleWorkspace: () => ({
    readExecutor: { run: vi.fn() },
  }),
}));

vi.mock("../domain/lifecycle-clients.js", () => ({
  createLifecycleClients: mockCreateLifecycleClients,
}));

vi.mock("../../lifecycle/useLifecycleExplorer.js", () => ({
  useLifecycleExplorer: mockUseLifecycleExplorer,
}));

const emptyState = (): LifecycleState => ({
  artifactList: {
    phase: "loaded",
    value: { items: [], total: 0, nextCursor: null },
  },
  deploymentList: { phase: "loaded", value: { items: [] } },
  runList: {
    phase: "loaded",
    value: { items: [], total: 0, nextCursor: null },
  },
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

const controller = (state: LifecycleState = emptyState()): LifecycleExplorerController => ({
  state,
  selectArtifact: vi.fn(),
  selectDeployment: vi.fn(),
  selectRun: vi.fn(),
  refresh: vi.fn(),
  loadMoreArtifacts: vi.fn(),
  loadMoreRuns: vi.fn(),
  loadTrace: vi.fn(),
});

const LocationProbe = () => <output data-testid="location">{useLocation().pathname}</output>;

const renderRoute = (entry: string) =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/console/artifacts" element={<LifecycleRoute kind="artifact" />} />
        <Route path="/console/artifacts/:artifactId/:version" element={<LifecycleRoute kind="artifact" />} />
        <Route path="/console/deployments" element={<LifecycleRoute kind="deployment" />} />
        <Route path="/console/deployments/:deploymentId" element={<LifecycleRoute kind="deployment" />} />
        <Route path="/console/runs" element={<LifecycleRoute kind="run" />} />
        <Route path="/console/runs/:runId" element={<LifecycleRoute kind="run" />} />
      </Routes>
      <LocationProbe />
    </MemoryRouter>,
  );

beforeEach(() => {
  mockCreateLifecycleClients.mockReset().mockReturnValue({
    artifacts: {},
    deployments: {},
    runs: {},
  });
  mockUseLifecycleExplorer.mockReset().mockReturnValue(controller());
});

afterEach(() => cleanup());

describe("LifecycleRoute", () => {
  it.each([
    ["/console/artifacts/report/2", "artifact", "selectArtifact", "report@2", "Artifacts"],
    ["/console/deployments/report.default", "deployment", "selectDeployment", "report.default", "Deployments"],
    ["/console/runs/run_123", "run", "selectRun", "run_123", "Runs"],
  ] as const)("synchronizes %s with the %s selection", async (entry, kind, selector, identity, heading) => {
    const currentController = controller();
    mockUseLifecycleExplorer.mockReturnValue(currentController);

    renderRoute(entry);

    expect(await screen.findByRole("heading", { name: heading, level: 1 })).toBeInTheDocument();
    await waitFor(() => {
      expect(currentController[selector]).toHaveBeenCalledWith(identity);
    });
    expect(mockCreateLifecycleClients).toHaveBeenCalledTimes(1);
    expect(mockUseLifecycleExplorer).toHaveBeenCalledWith(
      expect.objectContaining({ artifacts: {}, deployments: {}, runs: {} }),
    );
    expect(kind).toBeDefined();
  });

  it("renders a collection without selecting a record", async () => {
    const currentController = controller();
    mockUseLifecycleExplorer.mockReturnValue(currentController);

    renderRoute("/console/artifacts");

    expect(await screen.findByRole("heading", { name: "Artifacts", level: 1 })).toBeInTheDocument();
    expect(currentController.selectArtifact).not.toHaveBeenCalled();
  });

  it("suppresses stale detail synchronously until it matches the URL identity", () => {
    const currentController = controller({
      ...emptyState(),
      selectedArtifactId: "old@1",
      artifactDetail: {
        artifactId: "old",
        version: 1,
        title: "Old artifact",
        kind: "workflow",
        description: null,
        outcomes: [],
        plan: { nodes: [], edges: [] },
        requiredCapabilities: [],
        workflowDependencies: {},
        createdFromCatalogVersion: null,
      },
    });
    mockUseLifecycleExplorer.mockReturnValue(currentController);

    renderRoute("/console/artifacts/report/2");

    expect(screen.queryByText("Old artifact")).toBeNull();
    expect(currentController.selectArtifact).toHaveBeenCalledWith("report@2");
  });

  it("navigates to the canonical detail URL before selection follows it", async () => {
    const currentController = controller({
      ...emptyState(),
      artifactList: {
      phase: "loaded",
      value: {
        items: [
          {
            key: "report@2",
            artifactId: "report",
            version: 2,
            kind: "workflow",
            displayName: "Report",
            description: null,
            outcomes: ["ok"],
            requiredSources: [],
            diagnosticCount: 0,
          },
        ],
        total: 1,
        nextCursor: null,
      },
      },
    });
    mockUseLifecycleExplorer.mockReturnValue(currentController);

    renderRoute("/console/artifacts");
    await userEvent.click(screen.getByRole("option", { name: /Report version 2/i }));

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/console/artifacts/report/2");
      expect(currentController.selectArtifact).toHaveBeenCalledWith("report@2");
    });
  });
});

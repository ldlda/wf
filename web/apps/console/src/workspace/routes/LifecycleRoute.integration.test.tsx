import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { LifecycleClients } from "../domain/lifecycle-clients.js";
import type { ArtifactDetail, ArtifactList, DeploymentList, RunList } from "../../lifecycle/models.js";
import { LifecycleRoute } from "./LifecycleRoute.js";

const { mockCreateLifecycleClients } = vi.hoisted(() => ({
  mockCreateLifecycleClients: vi.fn(),
}));

vi.mock("../context.js", () => ({
  useConsoleWorkspace: () => ({
    readExecutor: { run: vi.fn() },
  }),
}));

vi.mock("../domain/lifecycle-clients.js", () => ({
  createLifecycleClients: mockCreateLifecycleClients,
}));

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const artifactList: ArtifactList = { items: [], total: 0, nextCursor: null };
const deploymentList: DeploymentList = { items: [] };
const runList: RunList = { items: [], total: 0, nextCursor: null };
const artifactDetail = {
  artifactId: "report",
  version: 2,
  title: "Report",
  kind: "workflow",
  description: null,
  outcomes: [],
  plan: { nodes: [], edges: [] },
  requiredCapabilities: [],
  workflowDependencies: {},
  createdFromCatalogVersion: null,
} satisfies ArtifactDetail;

const renderRoute = () =>
  render(
    <MemoryRouter initialEntries={["/console/artifacts/report/2"]}>
      <Routes>
        <Route path="/console/artifacts/:artifactId/:version" element={<LifecycleRoute kind="artifact" />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => mockCreateLifecycleClients.mockReset());
afterEach(() => cleanup());

describe("LifecycleRoute direct collection loading", () => {
  it("settles all collection loads after a direct detail route selects first", async () => {
    const artifacts = deferred<ArtifactList>();
    const deployments = deferred<DeploymentList>();
    const runs = deferred<RunList>();
    const clients: LifecycleClients = {
      artifacts: {
        list: vi.fn().mockReturnValue(artifacts.promise),
        inspect: vi.fn().mockResolvedValue(artifactDetail),
      },
      deployments: {
        list: vi.fn().mockReturnValue(deployments.promise),
        inspect: vi.fn(),
        validate: vi.fn(),
      },
      runs: {
        list: vi.fn().mockReturnValue(runs.promise),
        inspect: vi.fn(),
        trace: vi.fn(),
      },
    };
    mockCreateLifecycleClients.mockReturnValue(clients);

    renderRoute();
    await waitFor(() => {
      expect(clients.artifacts.list).toHaveBeenCalledWith({ limit: 50 });
      expect(clients.deployments.list).toHaveBeenCalledWith();
      expect(clients.runs.list).toHaveBeenCalledWith({ limit: 50 });
      expect(clients.artifacts.inspect).toHaveBeenCalledWith("report", 2);
    });
    expect(screen.getAllByRole("status")).toHaveLength(3);

    await act(async () => {
      artifacts.resolve(artifactList);
      deployments.resolve(deploymentList);
      runs.resolve(runList);
      await Promise.all([artifacts.promise, deployments.promise, runs.promise]);
    });

    await waitFor(() => {
      expect(screen.queryAllByRole("status")).toHaveLength(0);
      expect(screen.getByText("Report")).toBeVisible();
    });
  });
});

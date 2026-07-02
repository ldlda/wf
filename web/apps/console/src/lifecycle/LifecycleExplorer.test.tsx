import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { LifecycleExplorer } from "./LifecycleExplorer.js";

afterEach(() => {
  cleanup();
});
import type { LifecycleExplorerController } from "./useLifecycleExplorer.js";
import type { LifecycleState } from "./state.js";

const createMockController = (
  overrides: Partial<LifecycleState> = {},
): LifecycleExplorerController => ({
  state: {
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
    rawEvidence: [],
    errors: [],
    ...overrides,
  },
  selectArtifact: vi.fn(),
  selectDeployment: vi.fn(),
  selectRun: vi.fn(),
  refresh: vi.fn(),
  loadMoreArtifacts: vi.fn(),
  loadMoreRuns: vi.fn(),
  loadTrace: vi.fn(),
});

describe("LifecycleExplorer", () => {
  it("renders artifact buttons when loaded", () => {
    const controller = createMockController({
      artifactList: {
        phase: "loaded",
        value: {
          items: [
            {
              key: "report@1",
              artifactId: "report",
              version: 1,
              kind: "workflow",
              displayName: "Report",
              description: null,
              outcomes: ["ok"],
              requiredSources: ["local.report"],
              diagnosticCount: 0,
            },
          ],
          total: 1,
          nextCursor: null,
        },
      },
    });

    render(<LifecycleExplorer controller={controller} />);
    expect(screen.getByRole("option", { name: /Report version 1/i })).toBeVisible();
  });

  it("renders deployment buttons when loaded", () => {
    const controller = createMockController({
      deploymentList: {
        phase: "loaded",
        value: {
          items: [
            {
              id: "report.default",
              artifactId: "report",
              artifactVersion: 1,
              bindingCount: 1,
              driftPolicy: "block",
            },
          ],
        },
      },
    });

    render(<LifecycleExplorer controller={controller} />);
    expect(screen.getByRole("option", { name: /report.default/i })).toBeVisible();
  });

  it("renders run buttons when loaded", () => {
    const controller = createMockController({
      runList: {
        phase: "loaded",
        value: {
          items: [
            {
              runId: "run_1",
              deploymentId: "report.default",
              artifactId: "report",
              artifactVersion: 1,
              status: "interrupted",
              resumeReadiness: "ready",
              diagnosticCount: 0,
            },
          ],
          total: 1,
          nextCursor: null,
        },
      },
    });

    render(<LifecycleExplorer controller={controller} />);
    expect(screen.getByRole("option", { name: /run_1 interrupted/i })).toBeVisible();
  });

  it("calls selectArtifact when artifact is clicked", () => {
    const controller = createMockController({
      artifactList: {
        phase: "loaded",
        value: {
          items: [
            {
              key: "report@1",
              artifactId: "report",
              version: 1,
              kind: "workflow",
              displayName: "Report",
              description: null,
              outcomes: ["ok"],
              requiredSources: ["local.report"],
              diagnosticCount: 0,
            },
          ],
          total: 1,
          nextCursor: null,
        },
      },
    });

    render(<LifecycleExplorer controller={controller} />);
    fireEvent.click(screen.getAllByRole("option", { name: /Report version 1/i })[0]!);
    expect(controller.selectArtifact).toHaveBeenCalledWith("report@1");
  });

  it("shows empty state when no artifacts", () => {
    const controller = createMockController({
      artifactList: { phase: "loaded", value: { items: [], total: 0, nextCursor: null } },
    });

    render(<LifecycleExplorer controller={controller} />);
    expect(screen.getAllByText(/no artifacts/i)[0]).toBeVisible();
  });
});

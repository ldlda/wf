import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useLifecycleExplorer } from "./useLifecycleExplorer.js";

const mockCallOperation = vi.fn();
vi.mock("../connection/api.js", () => ({
  callOperation: (...args: unknown[]) => mockCallOperation(...args),
}));

beforeEach(() => {
  mockCallOperation.mockReset();
});

describe("useLifecycleExplorer", () => {
  it("loads artifact, deployment, and run lists on target change", async () => {
    mockCallOperation.mockResolvedValue({
      ok: true,
      operation: "workflow.artifacts.list",
      interpreted: { items: [], total: 0, nextCursor: null },
      exchange: { request: {}, response: {} },
      equivalentCli: "uv run wf artifact list",
      durationMs: 5,
    });

    const recordEvidence = vi.fn();
    const { result } = renderHook(() =>
      useLifecycleExplorer("http://127.0.0.1:8000/rpc", recordEvidence),
    );

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    expect(mockCallOperation).toHaveBeenCalledWith(
      "workflow.artifacts.list",
      "http://127.0.0.1:8000/rpc",
      expect.objectContaining({ limit: 50 }),
    );
  });

  it("selects an artifact and requests inspect", async () => {
    mockCallOperation.mockImplementation(async (operation: string) => {
      if (operation === "workflow.artifacts.inspect") {
        return {
          ok: true,
          operation: "workflow.artifacts.inspect",
          interpreted: {
            artifactId: "report",
            version: 1,
            title: "Report",
            kind: "workflow",
            description: null,
            outcomes: ["ok"],
            plan: { nodes: [], edges: [] },
            requiredCapabilities: [],
            workflowDependencies: {},
            createdFromCatalogVersion: null,
          },
          exchange: { request: {}, response: {} },
          equivalentCli: "uv run wf artifact inspect report --version 1",
          durationMs: 5,
        };
      }
      return {
        ok: true,
        operation,
        interpreted: {},
        exchange: { request: {}, response: {} },
        equivalentCli: "",
        durationMs: 5,
      };
    });

    const recordEvidence = vi.fn();
    const { result } = renderHook(() =>
      useLifecycleExplorer("http://127.0.0.1:8000/rpc", recordEvidence),
    );

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    await act(async () => {
      result.current.selectArtifact("report@1");
    });

    expect(mockCallOperation).toHaveBeenCalledWith(
      "workflow.artifacts.inspect",
      "http://127.0.0.1:8000/rpc",
      expect.objectContaining({ artifact_id: "report", version: 1 }),
    );
  });

  it("keeps deployment inspect and validation results from the same selection", async () => {
    mockCallOperation.mockImplementation(async (operation: string) => {
      if (operation === "workflow.deployments.inspect") {
        return {
          ok: true,
          operation,
          interpreted: {
            id: "report.default",
            artifactId: "report",
            artifactVersion: 1,
            bindings: [],
            driftPolicy: "block",
          },
          exchange: { request: {}, response: {} },
          equivalentCli: "uv run wf deploy inspect report.default",
          durationMs: 5,
        };
      }
      if (operation === "workflow.deployments.validate") {
        return {
          ok: true,
          operation,
          interpreted: {
            deploymentId: "report.default",
            artifactId: "report",
            artifactVersion: 1,
            status: "runnable",
            diagnostics: [],
            nextActions: {
              canContinue: true,
              canSaveNow: null,
              recommendedNextTool: null,
              reason: "deployment is runnable",
              patchExamples: [],
              warnings: [],
            },
          },
          exchange: { request: {}, response: {} },
          equivalentCli: "uv run wf deploy validate report.default",
          durationMs: 5,
        };
      }
      return {
        ok: true,
        operation,
        interpreted:
          operation === "workflow.deployments.list"
            ? { items: [] }
            : { items: [], total: 0, nextCursor: null },
        exchange: { request: {}, response: {} },
        equivalentCli: "",
        durationMs: 5,
      };
    });

    const recordEvidence = vi.fn();
    const { result } = renderHook(() =>
      useLifecycleExplorer("http://127.0.0.1:8000/rpc", recordEvidence),
    );

    await act(async () => {
      result.current.selectDeployment("report.default");
    });

    await waitFor(() => {
      expect(result.current.state.deploymentDetail?.id).toBe("report.default");
      expect(result.current.state.deploymentValidation?.status).toBe("runnable");
    });
  });

  it("ignores stale responses after target change", async () => {
    let callCount = 0;
    mockCallOperation.mockImplementation(async () => {
      callCount++;
      if (callCount === 1) {
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      return {
        ok: true,
        operation: "workflow.artifacts.list",
        interpreted: { items: [], total: 0, nextCursor: null },
        exchange: { request: {}, response: {} },
        equivalentCli: "uv run wf artifact list",
        durationMs: 5,
      };
    });

    const recordEvidence = vi.fn();
    const { result, rerender } = renderHook(
      ({ target }) => useLifecycleExplorer(target, recordEvidence),
      { initialProps: { target: "http://first-target/rpc" } },
    );

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    rerender({ target: "http://second-target/rpc" });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 150));
    });

    expect(mockCallOperation).toHaveBeenCalledWith(
      "workflow.artifacts.list",
      "http://second-target/rpc",
      expect.anything(),
    );
  });
});

import { describe, it, expect } from "vitest";
import {
  lifecycleReducer,
  initialLifecycleState,
  type LifecycleState,
  type LifecycleAction,
} from "./state.js";

describe("lifecycleReducer", () => {
  it("selectArtifact clears deployment and run selections", () => {
    const state: LifecycleState = {
      ...initialLifecycleState,
      selectedArtifactId: "old@1",
      selectedDeploymentId: "old.default",
      selectedRunId: "run_1",
      deploymentDetail: { id: "old.default" } as LifecycleState["deploymentDetail"],
      runDetail: { runId: "run_1" } as LifecycleState["runDetail"],
      trace: { frames: [], traceStart: 0, traceLimit: 50, traceTruncated: false } as LifecycleState["trace"],
    };

    const result = lifecycleReducer(state, {
      type: "selectArtifact",
      artifactId: "report@1",
    });

    expect(result.selectedArtifactId).toBe("report@1");
    expect(result.selectedDeploymentId).toBeNull();
    expect(result.selectedRunId).toBeNull();
    expect(result.deploymentDetail).toBeNull();
    expect(result.runDetail).toBeNull();
    expect(result.trace).toBeNull();
  });

  it("selectDeployment clears run selection", () => {
    const state: LifecycleState = {
      ...initialLifecycleState,
      selectedArtifactId: "report@1",
      selectedDeploymentId: "old.default",
      selectedRunId: "run_1",
      runDetail: { runId: "run_1" } as LifecycleState["runDetail"],
      trace: { frames: [], traceStart: 0, traceLimit: 50, traceTruncated: false } as LifecycleState["trace"],
    };

    const result = lifecycleReducer(state, {
      type: "selectDeployment",
      deploymentId: "report.default",
    });

    expect(result.selectedDeploymentId).toBe("report.default");
    expect(result.selectedRunId).toBeNull();
    expect(result.runDetail).toBeNull();
    expect(result.trace).toBeNull();
  });

  it("targetChanged resets to initial state", () => {
    const state: LifecycleState = {
      ...initialLifecycleState,
      selectedArtifactId: "report@1",
      artifactList: { phase: "loaded", value: { items: [], total: 0, nextCursor: null } },
    };

    const result = lifecycleReducer(state, { type: "targetChanged" });

    expect(result).toEqual(initialLifecycleState);
  });

  it("handles loading states", () => {
    const state = initialLifecycleState;

    const result = lifecycleReducer(state, {
      type: "setArtifactListPhase",
      phase: "loading",
    });

    expect(result.artifactList.phase).toBe("loading");
  });

  it("handles loaded states", () => {
    const state = initialLifecycleState;

    const result = lifecycleReducer(state, {
      type: "setArtifactListPhase",
      phase: "loaded",
      value: { items: [], total: 0, nextCursor: null },
    });

    expect(result.artifactList.phase).toBe("loaded");
  });

  it("handles error states", () => {
    const state = initialLifecycleState;

    const result = lifecycleReducer(state, {
      type: "setArtifactListPhase",
      phase: "error",
      message: "failed to load",
    });

    expect(result.artifactList.phase).toBe("error");
  });

  it("appendArtifactList merges new items with existing", () => {
    const state: LifecycleState = {
      ...initialLifecycleState,
      artifactList: {
        phase: "loaded",
        value: {
          items: [
            { key: "report@1", artifactId: "report", version: 1, kind: "workflow", displayName: "Report", description: null, outcomes: ["ok"], requiredSources: [], diagnosticCount: 0 },
          ],
          total: 2,
          nextCursor: "cursor_1",
        },
      },
    };

    const result = lifecycleReducer(state, {
      type: "appendArtifactList",
      value: {
        items: [
          { key: "summary@1", artifactId: "summary", version: 1, kind: "workflow", displayName: "Summary", description: null, outcomes: ["ok"], requiredSources: [], diagnosticCount: 0 },
        ],
        total: 2,
        nextCursor: null,
      },
    });

    if (result.artifactList.phase !== "loaded") throw new Error("expected loaded");
    expect(result.artifactList.value.items).toHaveLength(2);
    expect(result.artifactList.value.items[0]!.artifactId).toBe("report");
    expect(result.artifactList.value.items[1]!.artifactId).toBe("summary");
    expect(result.artifactList.value.nextCursor).toBeNull();
  });

  it("appendRunList merges new items with existing", () => {
    const state: LifecycleState = {
      ...initialLifecycleState,
      runList: {
        phase: "loaded",
        value: {
          items: [
            { runId: "run_1", deploymentId: "report.default", artifactId: "report", artifactVersion: 1, status: "interrupted", resumeReadiness: "ready", diagnosticCount: 0 },
          ],
          total: 2,
          nextCursor: "cursor_1",
        },
      },
    };

    const result = lifecycleReducer(state, {
      type: "appendRunList",
      value: {
        items: [
          { runId: "run_2", deploymentId: "report.default", artifactId: "report", artifactVersion: 1, status: "completed", resumeReadiness: "none", diagnosticCount: 0 },
        ],
        total: 2,
        nextCursor: null,
      },
    });

    if (result.runList.phase !== "loaded") throw new Error("expected loaded");
    expect(result.runList.value.items).toHaveLength(2);
    expect(result.runList.value.items[0]!.runId).toBe("run_1");
    expect(result.runList.value.items[1]!.runId).toBe("run_2");
    expect(result.runList.value.nextCursor).toBeNull();
  });

  it("appendArtifactList initializes from idle state", () => {
    const result = lifecycleReducer(initialLifecycleState, {
      type: "appendArtifactList",
      value: {
        items: [
          { key: "report@1", artifactId: "report", version: 1, kind: "workflow", displayName: "Report", description: null, outcomes: ["ok"], requiredSources: [], diagnosticCount: 0 },
        ],
        total: 1,
        nextCursor: null,
      },
    });

    if (result.artifactList.phase !== "loaded") throw new Error("expected loaded");
    expect(result.artifactList.value.items).toHaveLength(1);
  });
});

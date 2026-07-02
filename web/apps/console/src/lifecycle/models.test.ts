import { describe, it, expect } from "vitest";
import {
  decodeArtifactList,
  decodeArtifactDetail,
  decodeDeploymentList,
  decodeDeploymentDetail,
  decodeDeploymentValidation,
  decodeRunList,
  decodeRunDetail,
  decodeTracePage,
} from "./models.js";

describe("decodeArtifactList", () => {
  it("decodes an artifact list into immutable summaries", () => {
    const result = decodeArtifactList({
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
      nextCursor: null,
      total: 1,
    });
    expect(result.items[0]?.key).toBe("report@1");
    expect(result.items[0]?.artifactId).toBe("report");
    expect(result.items[0]?.version).toBe(1);
  });

  it("handles empty list", () => {
    const result = decodeArtifactList({
      items: [],
      nextCursor: null,
      total: 0,
    });
    expect(result.items).toEqual([]);
    expect(result.total).toBe(0);
  });
});

describe("decodeArtifactDetail", () => {
  it("decodes an artifact detail with plan", () => {
    const result = decodeArtifactDetail({
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
    });
    expect(result.artifactId).toBe("report");
    expect(result.title).toBe("Report");
    expect(result.plan).toEqual({ nodes: [], edges: [] });
  });
});

describe("decodeDeploymentList", () => {
  it("decodes a deployment list", () => {
    const result = decodeDeploymentList({
      items: [
        {
          id: "report.default",
          artifactId: "report",
          artifactVersion: 1,
          bindingCount: 1,
          driftPolicy: "block",
        },
      ],
    });
    expect(result.items[0]?.id).toBe("report.default");
  });
});

describe("decodeDeploymentDetail", () => {
  it("decodes a deployment detail", () => {
    const result = decodeDeploymentDetail({
      id: "report.default",
      artifactId: "report",
      artifactVersion: 1,
      bindings: [{ logicalSource: "local.report", concreteSource: "report" }],
      driftPolicy: "block",
    });
    expect(result.id).toBe("report.default");
    expect(result.bindings).toHaveLength(1);
  });
});

describe("decodeDeploymentValidation", () => {
  it("decodes a deployment validation result", () => {
    const result = decodeDeploymentValidation({
      deploymentId: "report.default",
      artifactId: "report",
      artifactVersion: 1,
      status: "runnable",
      diagnostics: [],
      nextActions: {
        canContinue: true,
        canSaveNow: null,
        recommendedNextTool: null,
        reason: "deployment is valid",
        patchExamples: [],
        warnings: [],
      },
    });
    expect(result.status).toBe("runnable");
    expect(result.nextActions.canContinue).toBe(true);
  });
});

describe("decodeRunList", () => {
  it("decodes a run list", () => {
    const result = decodeRunList({
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
      nextCursor: null,
      total: 1,
    });
    expect(result.items[0]?.runId).toBe("run_1");
    expect(result.items[0]?.status).toBe("interrupted");
  });
});

describe("decodeRunDetail", () => {
  it("decodes a run detail with interrupt", () => {
    const result = decodeRunDetail({
      runId: "run_1",
      deploymentId: "report.default",
      artifactId: "report",
      artifactVersion: 1,
      status: "interrupted",
      resumeReadiness: "ready",
      interrupt: { kind: "review", payload: {}, outcomes: [] },
      outcome: null,
      error: null,
      output: null,
      diagnostics: [],
      traceCount: 0,
      nextActions: {
        canContinue: false,
        canSaveNow: null,
        recommendedNextTool: null,
        reason: "run is interrupted",
        patchExamples: [],
        warnings: [],
      },
    });
    expect(result.interrupt?.kind).toBe("review");
    expect(result.traceCount).toBe(0);
  });
});

describe("decodeTracePage", () => {
  it("decodes a trace page", () => {
    const result = decodeTracePage({
      frames: [
        {
          nodeId: "review",
          stepType: "interrupt",
          outcome: "submitted",
          resolvedInput: {},
          output: {},
          stateChanges: {},
        },
      ],
      traceStart: 0,
      traceLimit: 50,
      traceTruncated: false,
    });
    expect(result.frames[0]?.nodeId).toBe("review");
    expect(result.traceTruncated).toBe(false);
  });
});

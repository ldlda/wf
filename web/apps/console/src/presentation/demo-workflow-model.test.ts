import { describe, expect, it } from "vitest";
import type { DemoEvent } from "../demo/timeline/models.js";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import {
  demoBeatLensForBeat,
  graphExecutionForBeat,
  projectInterruptContract,
  projectOperationPresentation,
} from "./demo-workflow-model.js";

const requireEvent = (stage: DemoEvent["stage"]): DemoEvent => {
  const event = loadCanonicalDemoRecording().events.find((candidate) => candidate.stage === stage);
  if (!event) throw new Error(`canonical recording is missing ${stage}`);
  return event;
};

describe("demo workflow presentation model", () => {
  it("projects the canonical run without inventing display facts", () => {
    const event = requireEvent("run_start");

    expect(projectOperationPresentation(event)).toEqual({
      operation: "workflow.runs.start",
      status: "interrupted",
      durationMs: 88,
      command: "uv run wf run start lda_report_case_study.default --input '<json>'",
      deploymentId: "lda_report_case_study.default",
      runId: "run_recorded_lda_report",
      interruptKind: "issue_review",
    });
  });

  it("projects the canonical typed interrupt contract", () => {
    expect(projectInterruptContract(requireEvent("run_start"))).toEqual({
      kind: "issue_review",
      outcomes: ["submitted", "cancelled"],
      resumeSchema: { type: "object" },
      runId: "run_recorded_lda_report",
    });
  });

  it("degrades malformed interpreted data to bounded fallbacks", () => {
    const sparse: DemoEvent = {
      ...requireEvent("run_start"),
      operation: null,
      equivalentCli: null,
      interpreted: "malformed",
      rawResponse: null,
    };

    expect(projectOperationPresentation(sparse)).toMatchObject({
      operation: "run_start",
      status: "unknown",
      command: null,
      interruptKind: null,
    });
    expect(projectInterruptContract(sparse)).toBeNull();
  });

  it("maps storyboard beats to one continuous execution", () => {
    expect(graphExecutionForBeat("graph")).toEqual({
      completedNodeIds: ["read_docs"],
      currentNodeId: "build_report",
    });
    expect(graphExecutionForBeat("interrupt")).toEqual({
      completedNodeIds: ["read_docs", "build_report"],
      currentNodeId: "review_issues",
    });
    expect(graphExecutionForBeat("approval")).toEqual({
      completedNodeIds: ["read_docs", "build_report"],
      currentNodeId: "review_issues",
    });
  });
});

describe("demo beat lens", () => {
  it("defines a product-story phase for every Scene 9 and Scene 10 beat", () => {
    const beatIds = ["operation", "graph", "interrupt", "approval", "resume", "output", "trace"];

    expect(beatIds.map((beatId) => demoBeatLensForBeat(beatId).phase)).toEqual([
      "agent",
      "run",
      "interrupt",
      "interrupt",
      "resume",
      "evidence",
      "evidence",
    ]);
  });

  it("uses stable audience-facing labels for the demo climax", () => {
    expect(demoBeatLensForBeat("operation")).toMatchObject({
      eyebrow: "Agent handoff",
      headline: "Request becomes a workflow run",
      proofLabel: "workflow.runs.start",
    });
    expect(demoBeatLensForBeat("approval")).toMatchObject({
      eyebrow: "Typed human boundary",
      headline: "The run waits for an explicit resume decision",
      proofLabel: "issue_review",
    });
    expect(demoBeatLensForBeat("trace")).toMatchObject({
      eyebrow: "Evidence remains",
      headline: "The result can still be inspected after the demo",
      proofLabel: "trace frames",
    });
  });

  it("keeps graph execution continuity across the interrupt and resume beats", () => {
    expect(graphExecutionForBeat("approval")).toEqual(graphExecutionForBeat("interrupt"));
    expect(graphExecutionForBeat("resume")).toMatchObject({
      completedNodeIds: ["read_docs", "build_report", "review_issues"],
      currentNodeId: "create_issues",
    });
    expect(graphExecutionForBeat("trace")).toMatchObject({
      currentNodeId: "end_completed",
    });
  });
});

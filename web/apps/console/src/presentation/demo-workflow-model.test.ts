import { describe, expect, it } from "vitest";
import type { DemoEvent } from "../demo/timeline/models.js";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import {
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

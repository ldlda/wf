import { describe, expect, it } from "vitest";
import {
  agentTextMessage,
  agentToolCallPart,
  agentToolResultPart,
  approvalRequestPart,
  presentationActionPart,
} from "./events.js";

describe("agent events", () => {
  it("creates a standard assistant text message", () => {
    const message = agentTextMessage("m1", "assistant", "I will use a prepared recipe.");
    expect(message).toEqual({
      id: "m1",
      role: "assistant",
      parts: [{ type: "text", text: "I will use a prepared recipe." }],
    });
  });

  it("creates tool call, tool result, and presentation action parts", () => {
    expect(agentToolCallPart("c1", "startPreparedReportRun", { deploymentId: "lda_report_case_study.default" })).toEqual({
      type: "tool-call",
      call: {
        id: "c1",
        name: "startPreparedReportRun",
        input: { deploymentId: "lda_report_case_study.default" },
      },
    });
    expect(agentToolResultPart("c1", "startPreparedReportRun", "success", { runId: "run_1" })).toEqual({
      type: "tool-result",
      result: {
        callId: "c1",
        name: "startPreparedReportRun",
        status: "success",
        output: { runId: "run_1" },
      },
    });
    expect(presentationActionPart({ type: "selectWorkflowNode", nodeId: "review_issues" })).toEqual({
      type: "presentation-action",
      action: { type: "selectWorkflowNode", nodeId: "review_issues" },
    });
  });

  it("creates approval request part", () => {
    expect(approvalRequestPart("c1", "resumeIssueReview", "Approve the typed issue review?")).toEqual({
      type: "approval-request",
      callId: "c1",
      name: "resumeIssueReview",
      prompt: "Approve the typed issue review?",
    });
  });

  it("creates approval request parts with optional contract data", () => {
    const part = approvalRequestPart(
      "call-1",
      "resumeIssueReview",
      "Approve?",
      {
        kind: "issue_review",
        outcomes: ["submitted", "cancelled"],
        resumeSchema: { type: "object" },
        resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
        runId: "run_recorded_lda_report",
      },
    );

    expect(part).toMatchObject({
      type: "approval-request",
      contract: {
        kind: "issue_review",
        runId: "run_recorded_lda_report",
      },
    });
  });
});

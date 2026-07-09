import { describe, expect, it } from "vitest";
import type { AgentMessage } from "../../demo/agent/events.js";
import { projectAgentMessage } from "./agentChatProjection.js";

describe("agentChatProjection", () => {
  it("projects text parts", () => {
    const message: AgentMessage = {
      id: "m1",
      role: "assistant",
      parts: [{ type: "text", text: "Live target is ready." }],
    };

    expect(projectAgentMessage(message)).toMatchObject({
      id: "m1",
      from: "assistant",
      parts: [{ kind: "text", text: "Live target is ready." }],
    });
  });

  it("projects workflow start as an expanded workflow operation", () => {
    const message: AgentMessage = {
      id: "m1",
      role: "assistant",
      parts: [{ type: "tool-call", call: { id: "call-1", name: "startPreparedReportRun", input: { mode: "live" } } }],
    };

    expect(projectAgentMessage(message).parts[0]).toMatchObject({
      kind: "tool",
      label: "Workflow operation",
      name: "startPreparedReportRun",
      state: "pending",
      defaultOpen: true,
      input: { mode: "live" },
    });
  });

  it("projects ordinary tool results as collapsed tool records", () => {
    const message: AgentMessage = {
      id: "m1",
      role: "assistant",
      parts: [{ type: "tool-result", result: { callId: "call-1", name: "readRunTrace", status: "success", output: { frames: 4 } } }],
    };

    expect(projectAgentMessage(message).parts[0]).toMatchObject({
      kind: "tool",
      label: "Tool result",
      name: "readRunTrace",
      state: "success",
      defaultOpen: false,
      output: { frames: 4 },
    });
  });

  it("projects approval requests with their contract", () => {
    const message: AgentMessage = {
      id: "m1",
      role: "assistant",
      parts: [{
        type: "approval-request",
        callId: "call-1",
        name: "resumeIssueReview",
        prompt: "Submit resume request?",
        contract: {
          kind: "issue_review",
          outcomes: ["submitted", "cancelled"],
          resumeSchema: { type: "object" },
          resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
          runId: "run_1",
        },
      }],
    };

    expect(projectAgentMessage(message).parts[0]).toMatchObject({
      kind: "approval",
      name: "resumeIssueReview",
      prompt: "Submit resume request?",
      contract: { kind: "issue_review", runId: "run_1" },
    });
  });
});

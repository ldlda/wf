import { describe, expect, it } from "vitest";
import type { AgentMessage } from "../../demo/agent/events.js";
import { projectAgentMessagesForAssistant } from "./assistantRuntimeProjection.js";

describe("assistantRuntimeProjection", () => {
  it("projects text and tool call parts into assistant-ui content parts", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "assistant-1",
        role: "assistant",
        parts: [
          { type: "text", text: "I will inspect the run." },
          {
            type: "tool-call",
            call: { id: "call-1", name: "readRunTrace", input: { run_id: "run_1" } },
          },
        ],
      },
    ];

    const projected = projectAgentMessagesForAssistant(messages);

    expect(projected).toHaveLength(1);
    expect(projected[0]).toMatchObject({
      id: "assistant-1",
      role: "assistant",
    });
    expect(projected[0]?.content).toEqual([
      { type: "text", text: "I will inspect the run." },
      {
        type: "tool-call",
        toolCallId: "call-1",
        toolName: "readRunTrace",
        args: { run_id: "run_1" },
      },
    ]);
  });

  it("projects tool results as tool-role messages", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "tool-result-message",
        role: "assistant",
        parts: [
          {
            type: "tool-result",
            result: {
              callId: "call-1",
              name: "readRunTrace",
              status: "success",
              output: { frames: 3 },
            },
          },
        ],
      },
    ];

    const projected = projectAgentMessagesForAssistant(messages);

    expect(projected[0]).toMatchObject({
      id: "tool-result-message",
      role: "tool",
      content: [
        {
          type: "tool-result",
          toolCallId: "call-1",
          toolName: "readRunTrace",
          result: { frames: 3 },
          isError: false,
        },
      ],
    });
  });

  it("projects approval requests as human tool calls with contract metadata", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "approval",
        role: "assistant",
        parts: [
          {
            type: "approval-request",
            callId: "call-approval",
            name: "resumeIssueReview",
            prompt: "Submit resume request?",
            contract: {
              kind: "issue_review",
              outcomes: ["submitted", "cancelled"],
              resumeSchema: { type: "object" },
              resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
              runId: "run_recorded_lda_report",
            },
          },
        ],
      },
    ];

    const projected = projectAgentMessagesForAssistant(messages);

    expect(projected[0]?.content).toEqual([
      { type: "text", text: "Submit resume request?" },
      {
        type: "tool-call",
        toolCallId: "call-approval",
        toolName: "resumeIssueReview",
        args: {
          prompt: "Submit resume request?",
          contract: {
            kind: "issue_review",
            outcomes: ["submitted", "cancelled"],
            resumeSchema: { type: "object" },
            resumePayloadPreview: { selected_issue_ids: ["risk-1"] },
            runId: "run_recorded_lda_report",
          },
        },
      },
    ]);
  });

  it("keeps presentation actions and errors visible as text/tool evidence", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "mixed",
        role: "assistant",
        parts: [
          { type: "presentation-action", action: { type: "selectWorkflowNode", nodeId: "review_issues" } },
          { type: "error", message: "provider failed" },
        ],
      },
    ];

    const projected = projectAgentMessagesForAssistant(messages);

    expect(projected[0]?.content).toEqual([
      {
        type: "tool-call",
        toolCallId: "presentation-selectWorkflowNode",
        toolName: "presentation.selectWorkflowNode",
        args: { type: "selectWorkflowNode", nodeId: "review_issues" },
      },
      { type: "text", text: "provider failed" },
    ]);
  });
});

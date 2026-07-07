import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OperatorChat } from "./OperatorChat.js";
import { initialPresentationState } from "./presentation-state.js";
import type { AgentMessage } from "../demo/agent/events.js";

afterEach(() => cleanup());

describe("OperatorChat", () => {
  it("renders standard agent message parts", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      { id: "u1", role: "user", parts: [{ type: "text", text: "Prepare the report." }] },
      {
        id: "a1",
        role: "assistant",
        parts: [
          { type: "text", text: "I will use the prepared recipe." },
          {
            type: "tool-call",
            call: { id: "call-1", name: "selectWorkflowNode", input: { nodeId: "review_issues" } },
          },
          {
            type: "tool-result",
            result: { callId: "call-1", name: "selectWorkflowNode", status: "success", output: { nodeId: "review_issues" } },
          },
        ],
      },
    ];

    render(<OperatorChat state={initialPresentationState} messages={messages} />);

    expect(screen.getByText("Prepare the report.")).toBeInTheDocument();
    expect(screen.getByText("I will use the prepared recipe.")).toBeInTheDocument();
    expect(screen.getByText(/tool call/i)).toBeInTheDocument();
    expect(screen.getAllByText(/selectWorkflowNode/i).length).toBe(2);
    expect(screen.getByText(/tool result/i)).toBeInTheDocument();
  });

  it("renders fallback messages when no agent messages are present", () => {
    render(<OperatorChat state={initialPresentationState} />);

    expect(screen.getByText("Prepare the thesis readiness report.")).toBeInTheDocument();
    expect(screen.getByText(/Found prepared workflow recipe/)).toBeInTheDocument();
  });

  it("renders approval controls and wires decisions", async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    const onDeny = vi.fn();
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "approval",
        role: "assistant",
        parts: [
          {
            type: "approval-request",
            callId: "call-1",
            name: "resumeIssueReview",
            prompt: "Approve resuming?",
          },
        ],
      },
    ];

    render(<OperatorChat state={initialPresentationState} messages={messages} onApprove={onApprove} onDeny={onDeny} />);

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Deny" }));
    expect(onApprove).toHaveBeenCalledTimes(1);
    expect(onDeny).toHaveBeenCalledTimes(1);
  });

  it("renders error and presentation action parts", () => {
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

    render(<OperatorChat state={initialPresentationState} messages={messages} />);

    expect(screen.getByText("Presentation action")).toBeInTheDocument();
    expect(screen.getByText("selectWorkflowNode")).toBeInTheDocument();
    expect(screen.getByText("provider failed")).toBeInTheDocument();
  });

  it("renders prepared run tool calls as workflow handoffs", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "start",
        role: "assistant",
        parts: [
          {
            type: "tool-call",
            call: { id: "call-1", name: "startPreparedReportRun", input: { deploymentId: "demo" } },
          },
        ],
      },
    ];

    render(<OperatorChat state={initialPresentationState} messages={messages} />);

    expect(screen.getByText("Workflow operation")).toBeInTheDocument();
    expect(screen.getByText("startPreparedReportRun")).toBeInTheDocument();
  });
});

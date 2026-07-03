import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OperatorChat } from "./OperatorChat.js";
import type { PresentationState } from "./presentation-state.js";
import type { AgentMessage } from "../demo/agent/events.js";

const state: PresentationState = {
  beat: "intro",
  selectedNodeId: null,
  chatMode: "full",
  evidenceMode: "hidden",
  playbackMode: "replay",
};

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

    render(<OperatorChat state={state} messages={messages} />);

    expect(screen.getByText("Prepare the report.")).toBeInTheDocument();
    expect(screen.getByText("I will use the prepared recipe.")).toBeInTheDocument();
    expect(screen.getByText(/tool call/i)).toBeInTheDocument();
    expect(screen.getAllByText(/selectWorkflowNode/i).length).toBe(2);
    expect(screen.getByText(/tool result/i)).toBeInTheDocument();
  });
});

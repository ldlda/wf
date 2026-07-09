import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentMessage } from "../../demo/agent/events.js";
import { AssistantOperatorThread } from "./AssistantOperatorThread.js";

afterEach(() => cleanup());

describe("AssistantOperatorThread", () => {
  it("renders text interleaved with a collapsed tool call", async () => {
    const user = userEvent.setup();
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
          { type: "text", text: "The trace is inspectable." },
        ],
      },
    ];

    render(<AssistantOperatorThread mode="dock" messages={messages} />);

    expect(screen.getByRole("log", { name: /operator conversation/i })).toBeInTheDocument();
    expect(screen.getByText("I will inspect the run.")).toBeInTheDocument();
    expect(screen.getByText("The trace is inspectable.")).toBeInTheDocument();
    const tool = screen.getByRole("button", { name: /readRunTrace/i });
    expect(screen.queryByText(/run_1/)).not.toBeInTheDocument();
    await user.click(tool);
    expect(screen.getByText(/run_1/)).toBeInTheDocument();
  });

  it("renders grouped consecutive tool calls", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "assistant-tools",
        role: "assistant",
        parts: [
          { type: "tool-call", call: { id: "call-1", name: "readRunTrace", input: {} } },
          { type: "tool-call", call: { id: "call-2", name: "inspectDeployment", input: { deployment_id: "demo" } } },
        ],
      },
    ];

    render(<AssistantOperatorThread mode="dock" messages={messages} />);

    expect(screen.getByText(/2 tools/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /readRunTrace/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /inspectDeployment/i })).toBeInTheDocument();
  });

  it("renders schema approval through the existing approval surface", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    const cancel = vi.fn();
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

    render(
      <AssistantOperatorThread
        mode="dock"
        messages={messages}
        submitApproval={submit}
        cancelApproval={cancel}
      />,
    );

    expect(screen.getByRole("group", { name: /issue review resume/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(submit).toHaveBeenCalledOnce();
    expect(cancel).toHaveBeenCalledOnce();
  });

  it("renders a chat-owned run action", async () => {
    const user = userEvent.setup();
    const run = vi.fn();
    render(
      <AssistantOperatorThread
        mode="dock"
        messages={[]}
        runAction={{ label: "Run prepared workflow", disabled: false, run }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /run prepared workflow/i }));
    expect(run).toHaveBeenCalledOnce();
  });
});

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentMessage } from "../../demo/agent/events.js";
import { AssistantOperatorThread } from "./AssistantOperatorThread.js";

afterEach(() => cleanup());

describe("AssistantOperatorThread", () => {
  it("renders text interleaved with an open tool call", async () => {
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

    const { container } = render(<AssistantOperatorThread mode="dock" messages={messages} />);

    expect(screen.getByRole("log", { name: /operator conversation/i })).toBeInTheDocument();
    expect(container.querySelector('[data-slot="tool-fallback-root"]')).toBeInTheDocument();
    expect(screen.getByText("I will inspect the run.")).toBeInTheDocument();
    expect(screen.getByText("The trace is inspectable.")).toBeInTheDocument();
    const tool = screen.getByRole("button", { name: /readRunTrace/i });
    expect(tool).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/run_1/)).toBeInTheDocument();
    await user.click(tool);
    expect(screen.queryByText(/run_1/)).not.toBeInTheDocument();
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

    const { container } = render(<AssistantOperatorThread mode="dock" messages={messages} />);

    expect(container.querySelector('[data-slot="tool-group-root"]')).toBeInTheDocument();
    expect(screen.getByText(/2 tool calls/i)).toBeInTheDocument();
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

  it("labels and opens the synchronized authoring phase group", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "authoring-validate-tools",
        role: "assistant",
        parts: [
          { type: "tool-call", call: { id: "authoring-validate-command-0", name: "runWorkflowCommand", input: {} } },
          { type: "tool-result", result: { callId: "authoring-validate-command-0", name: "runWorkflowCommand", status: "success", output: {} } },
        ],
      },
    ];

    render(
      <AssistantOperatorThread
        mode="dock"
        surface="dock"
        messages={messages}
        activeToolGroupId="authoring-validate"
      />,
    );

    expect(screen.getByRole("log")).toHaveAttribute("data-surface", "dock");
    expect(screen.getByRole("button", { name: /validate.*1 tool call/i }))
      .toHaveAttribute("aria-expanded", "true");
  });

  it("scrolls the active authoring group into the dock viewport", async () => {
    const setScrollTop = vi.fn();
    Object.defineProperty(HTMLDivElement.prototype, "scrollTop", {
      configurable: true,
      get: () => 0,
      set: setScrollTop,
    });
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "authoring-draft-tools",
        role: "assistant",
        parts: [
          { type: "tool-call", call: { id: "authoring-draft-command-0", name: "runWorkflowCommand", input: {} } },
          { type: "tool-result", result: { callId: "authoring-draft-command-0", name: "runWorkflowCommand", status: "success", output: {} } },
        ],
      },
    ];

    render(
      <AssistantOperatorThread
        mode="dock"
        surface="dock"
        messages={messages}
        activeToolGroupId="authoring-draft"
      />,
    );

    await waitFor(() => expect(setScrollTop).toHaveBeenCalledWith(0));
  });

  it("renders structured tool results through the generated fallback result slot", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "assistant-result",
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

    const { container } = render(<AssistantOperatorThread mode="dock" messages={messages} />);

    expect(container.querySelector('[data-slot="tool-fallback-result"]')).toBeInTheDocument();
    expect(screen.getByText(/"frames": 3/)).toBeInTheDocument();
  });
});

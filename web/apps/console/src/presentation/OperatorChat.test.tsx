import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OperatorChat } from "./OperatorChat.js";
import { initialPresentationState } from "./presentation-state.js";
import type { AgentMessage } from "../demo/agent/events.js";

afterEach(() => cleanup());

describe("OperatorChat", () => {
  it("maps light chat theme to the editorial presentation surface", () => {
    const state = {
      ...initialPresentationState,
      location: { kind: "main" as const, sceneId: "run-from-deployment" as const, beatId: "graph", focusPath: [] },
    };

    render(<OperatorChat state={state} />);

    const chat = screen.getByLabelText("scripted operator chat");
    expect(chat).toHaveAttribute("data-chat-theme", "light");
    expect(chat).toHaveAttribute("data-presentation-surface", "editorial");
    expect(screen.getAllByText(/Found prepared workflow recipe/)[0]?.closest(".ai-chat-message"))
      .toHaveClass("ai-chat-message");
  });

  it("maps dark chat theme to the night presentation surface", () => {
    render(<OperatorChat state={initialPresentationState} />);

    const chat = screen.getByLabelText("scripted operator chat");
    expect(chat).toHaveAttribute("data-presentation-surface", "night");
  });

  it("exposes semantic chat surface attributes", () => {
    render(<OperatorChat state={initialPresentationState} />);

    const chat = screen.getByLabelText("scripted operator chat");
    expect(chat).toHaveAttribute("data-chat-theme");
    expect(chat).not.toHaveAttribute("data-readable-surface");
  });

  it("renders messages through the AI chat conversation surface", () => {
    render(<OperatorChat state={initialPresentationState} />);

    expect(screen.getByRole("log", { name: "operator conversation" })).toBeInTheDocument();
    expect(screen.getByText("Prepare the thesis readiness report.")).toBeInTheDocument();
  });

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

  it("renders tool calls as collapsed AI tool blocks", async () => {
    const user = userEvent.setup();
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "start",
        role: "assistant",
        parts: [
          { type: "tool-call", call: { id: "call-1", name: "readRunTrace", input: { run_id: "run_1" } } },
        ],
      },
    ];

    render(<OperatorChat state={initialPresentationState} messages={messages} />);

    const tool = screen.getByRole("button", { name: /tool call.*readRunTrace/i });
    expect(screen.queryByText(/run_id/)).not.toBeInTheDocument();
    await user.click(tool);
    expect(screen.getByText(/run_id/)).toBeInTheDocument();
  });

  it("renders fallback messages when no agent messages are present", () => {
    render(<OperatorChat state={initialPresentationState} />);

    expect(screen.getByText("Prepare the thesis readiness report.")).toBeInTheDocument();
    expect(screen.getByText(/Found prepared workflow recipe/)).toBeInTheDocument();
  });

  it("renders schema approval surface inside chat approval request", async () => {
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
            prompt: "Submit resume request?",
            contract: {
              kind: "issue_review",
              outcomes: ["submitted", "cancelled"],
              resumeSchema: { type: "object", properties: { comment: { type: "string" } } },
              resumePayloadPreview: { comment: "Looks good." },
              runId: "run_recorded_lda_report",
            },
          },
        ],
      },
    ];

    render(<OperatorChat state={initialPresentationState} messages={messages} onApprove={onApprove} onDeny={onDeny} />);

    expect(screen.getByRole("group", { name: /issue review resume/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /submit/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onApprove).toHaveBeenCalledTimes(1);
    expect(onDeny).toHaveBeenCalledTimes(1);
  });

  it("falls back to plain approve/deny buttons when approval request has no contract", async () => {
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
            prompt: "Submit resume request?",
          },
        ],
      },
    ];

    render(<OperatorChat state={initialPresentationState} messages={messages} onApprove={onApprove} onDeny={onDeny} />);

    expect(screen.queryByRole("group", { name: /issue review resume/i })).not.toBeInTheDocument();
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

  it("shows a chat-owned run prepared workflow action", async () => {
    const user = userEvent.setup();
    const runPreparedWorkflow = vi.fn(async () => {});

    render(
      <OperatorChat
        state={initialPresentationState}
        timelineAgent={{
          messages: [],
          canRun: true,
          runLabel: "Run prepared workflow",
          runPreparedWorkflow,
          submitSelectedIssues: vi.fn(async () => {}),
          cancelReview: vi.fn(async () => {}),
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /run prepared workflow/i }));
    expect(runPreparedWorkflow).toHaveBeenCalledTimes(1);
  });

  it("routes schema approval submit and cancel through the timeline agent when present", async () => {
    const user = userEvent.setup();
    const submitSelectedIssues = vi.fn(async () => {});
    const cancelReview = vi.fn(async () => {});
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "approval",
        role: "assistant",
        parts: [
          {
            type: "approval-request",
            callId: "call-1",
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
      <OperatorChat
        state={initialPresentationState}
        messages={messages}
        timelineAgent={{
          messages: [],
          canRun: false,
          runLabel: "Run prepared workflow",
          runPreparedWorkflow: vi.fn(async () => {}),
          submitSelectedIssues,
          cancelReview,
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /submit/i }));
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(submitSelectedIssues).toHaveBeenCalledTimes(1);
    expect(cancelReview).toHaveBeenCalledTimes(1);
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

  it("disables schema approval buttons when approval actions are unavailable", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "approval",
        role: "assistant",
        parts: [
          {
            type: "approval-request",
            callId: "call-1",
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
      <OperatorChat
        state={initialPresentationState}
        messages={messages}
        onApprove={undefined}
        onDeny={undefined}
      />,
    );

    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("routes approval requests through provided approval callbacks", async () => {
    const user = userEvent.setup();
    const approve = vi.fn();
    const deny = vi.fn();
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "approval",
        role: "assistant",
        parts: [
          {
            type: "approval-request",
            callId: "call-1",
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
      <OperatorChat
        state={initialPresentationState}
        messages={messages}
        onApprove={approve}
        onDeny={deny}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(approve).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(deny).toHaveBeenCalledOnce();
  });
});

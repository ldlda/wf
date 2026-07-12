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

  it("renders through the assistant-ui operator thread", () => {
    render(<OperatorChat state={initialPresentationState} />);

    expect(screen.getByRole("log", { name: /operator conversation/i }))
      .toHaveClass("assistant-operator-thread");
  });

  it("renders fallback messages when no agent messages are present", () => {
    render(<OperatorChat state={initialPresentationState} />);

    expect(screen.getByText("Prepare the thesis readiness report.")).toBeInTheDocument();
    expect(screen.getByText(/Found prepared workflow recipe/)).toBeInTheDocument();
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
    expect(screen.getAllByRole("button", { name: /selectWorkflowNode/i }).length).toBeGreaterThan(0);
  });

  it("renders tool calls as open tool cards", async () => {
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

    const tool = screen.getByRole("button", { name: /readRunTrace/i });
    expect(tool).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(/run_1/)).toBeInTheDocument();
    await user.click(tool);
    expect(screen.queryByText(/run_1/)).not.toBeInTheDocument();
  });

  it("renders schema approval surface inside chat approval request", async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();
    const onRequestRevision = vi.fn();
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

    render(<OperatorChat state={initialPresentationState} messages={messages} onApprove={onApprove} onRequestRevision={onRequestRevision} />);

    expect(screen.getByRole("group", { name: /issue review resume/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /submit/i }));
    await user.click(screen.getByRole("button", { name: /request revision/i }));
    expect(onApprove).toHaveBeenCalledTimes(1);
    expect(onRequestRevision).toHaveBeenCalledTimes(1);
  });

  it("falls back to tool card display when approval request has no contract", async () => {
    const user = userEvent.setup();
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

    const { container } = render(<OperatorChat state={initialPresentationState} messages={messages} />);

    expect(screen.queryByRole("group", { name: /issue review resume/i })).not.toBeInTheDocument();
    expect(screen.getByText("Submit resume request?")).toBeInTheDocument();
    const tool = screen.getByRole("button", { name: /resumeIssueReview/i });
    expect(screen.queryByRole("button", { name: /Approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Deny/i })).not.toBeInTheDocument();
    expect(container.querySelector('[data-slot="tool-fallback-args"]')).toBeInTheDocument();
    await user.click(tool);
    expect(container.querySelector('[data-slot="tool-fallback-args"]')).not.toBeInTheDocument();
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

    expect(screen.getByText("provider failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /presentation.selectWorkflowNode/i })).toBeInTheDocument();
  });

  it("does not render the run prepared workflow action", () => {
    const runPreparedWorkflow = vi.fn(async () => {});

    render(
      <OperatorChat
        state={initialPresentationState}
        timelineAgent={{
          messages: [],
          canRun: true,
          canRunLive: true,
          runLabel: "Run prepared workflow",
          runPreparedWorkflow,
          submitSelectedIssues: vi.fn(async () => {}),
          requestRevision: vi.fn(async () => {}),
        }}
      />,
    );

    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
    expect(runPreparedWorkflow).not.toHaveBeenCalled();
  });

  it("routes schema approval submit and revision request through the timeline agent when present", async () => {
    const user = userEvent.setup();
    const submitSelectedIssues = vi.fn(async () => {});
    const requestRevision = vi.fn(async () => {});
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
          canRunLive: false,
          runLabel: "Run prepared workflow",
          runPreparedWorkflow: vi.fn(async () => {}),
          submitSelectedIssues,
          requestRevision,
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /submit/i }));
    await user.click(screen.getByRole("button", { name: /request revision/i }));
    expect(submitSelectedIssues).toHaveBeenCalledTimes(1);
    expect(requestRevision).toHaveBeenCalledTimes(1);
  });

  it("renders prepared run tool calls as workflow handoffs", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "start",
        role: "assistant",
        parts: [
          {
            type: "tool-call",
            call: { id: "call-1", name: "startRun", input: { deploymentId: "demo" } },
          },
        ],
      },
    ];

    render(<OperatorChat state={initialPresentationState} messages={messages} />);

    expect(screen.getByRole("button", { name: /startRun/i })).toBeInTheDocument();
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
        onRequestRevision={undefined}
      />,
    );

    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Request revision" })).toBeDisabled();
  });

  it("routes approval requests through provided approval callbacks", async () => {
    const user = userEvent.setup();
    const approve = vi.fn();
    const requestRevision = vi.fn();
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
        onRequestRevision={requestRevision}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Submit" }));
    expect(approve).toHaveBeenCalledOnce();

    await user.click(screen.getByRole("button", { name: "Request revision" }));
    expect(requestRevision).toHaveBeenCalledOnce();
  });
});

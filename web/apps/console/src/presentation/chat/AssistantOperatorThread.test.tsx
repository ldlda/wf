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
    const requestRevision = vi.fn();
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
        requestRevision={requestRevision}
      />,
    );

    expect(screen.getByRole("group", { name: /issue review resume/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await user.click(screen.getByRole("button", { name: "Request revision" }));
    expect(submit).toHaveBeenCalledOnce();
    expect(requestRevision).toHaveBeenCalledOnce();
  });

  it("does not render a run action", () => {
    render(<AssistantOperatorThread mode="dock" messages={[]} />);

    expect(screen.queryByRole("button", { name: /run prepared workflow/i })).not.toBeInTheDocument();
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
    const originalDescriptor = Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, "scrollTop");
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

    try {
      Object.defineProperty(HTMLDivElement.prototype, "scrollTop", {
        configurable: true,
        get: () => 0,
        set: setScrollTop,
      });
      render(
        <AssistantOperatorThread
          mode="dock"
          surface="dock"
          messages={messages}
          activeToolGroupId="authoring-draft"
        />,
      );

      await waitFor(() => expect(setScrollTop).toHaveBeenCalledWith(0));
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(HTMLDivElement.prototype, "scrollTop", originalDescriptor);
      } else {
        delete (HTMLDivElement.prototype as { scrollTop?: number }).scrollTop;
      }
    }
  });

  it("can keep a first-stage group anchored at the start of the transcript", async () => {
    const setScrollTop = vi.fn();
    const descriptors = {
      scrollTop: Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, "scrollTop"),
      scrollHeight: Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, "scrollHeight"),
      clientHeight: Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, "clientHeight"),
      offsetTop: Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetTop"),
      offsetHeight: Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetHeight"),
    };
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "assistant-start-scroll-text",
        role: "assistant",
        parts: [
          { type: "text", text: "The first authoring turn is visible." },
        ],
      },
      {
        id: "authoring-discover-tools",
        role: "assistant",
        parts: [
          { type: "tool-call", call: { id: "authoring-discover-command-0", name: "workflow.sources.list", input: { phase: "discover" } } },
          { type: "tool-result", result: { callId: "authoring-discover-command-0", name: "workflow.sources.list", status: "success", output: {} } },
        ],
      },
    ];

    try {
      Object.defineProperties(HTMLDivElement.prototype, {
        scrollTop: { configurable: true, get: () => 0, set: setScrollTop },
        scrollHeight: { configurable: true, get: () => 400 },
        clientHeight: { configurable: true, get: () => 80 },
      });
      Object.defineProperties(HTMLElement.prototype, {
        offsetTop: { configurable: true, get: () => 120 },
        offsetHeight: { configurable: true, get: () => 40 },
      });
      render(
        <AssistantOperatorThread
          mode="full"
          surface="stage"
          messages={messages}
          activeToolGroupId="authoring-discover"
          scrollMode="start"
        />,
      );

      await waitFor(() => expect(setScrollTop).toHaveBeenCalledWith(0));
    } finally {
      for (const [name, descriptor] of Object.entries(descriptors)) {
        const prototype = name === "offsetTop" || name === "offsetHeight"
          ? HTMLElement.prototype
          : HTMLDivElement.prototype;
        if (descriptor) {
          Object.defineProperty(prototype, name, descriptor);
        } else {
          delete (prototype as unknown as Record<string, unknown>)[name];
        }
      }
    }
  });

  it("can show the latest response in a static comparison transcript", async () => {
    const setScrollTop = vi.fn();
    const descriptors = {
      scrollTop: Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, "scrollTop"),
      scrollHeight: Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, "scrollHeight"),
      clientHeight: Object.getOwnPropertyDescriptor(HTMLDivElement.prototype, "clientHeight"),
    };

    try {
      Object.defineProperties(HTMLDivElement.prototype, {
        scrollTop: { configurable: true, get: () => 0, set: setScrollTop },
        scrollHeight: { configurable: true, get: () => 240 },
        clientHeight: { configurable: true, get: () => 80 },
      });
      render(<AssistantOperatorThread mode="dock" messages={[]} scrollMode="end" />);

      await waitFor(() => expect(setScrollTop).toHaveBeenCalledWith(160));
    } finally {
      for (const [name, descriptor] of Object.entries(descriptors)) {
        if (descriptor) {
          Object.defineProperty(HTMLDivElement.prototype, name, descriptor);
        } else {
          delete (HTMLDivElement.prototype as unknown as Record<string, unknown>)[name];
        }
      }
    }
  });

  it("pairs a lone tool call with its result", () => {
    const messages: ReadonlyArray<AgentMessage> = [
      {
        id: "assistant-tool-result",
        role: "assistant",
        parts: [
          { type: "tool-call", call: { id: "call-1", name: "readRunTrace", input: {} } },
          { type: "tool-result", result: { callId: "call-1", name: "readRunTrace", status: "success", output: { frames: 3 } } },
        ],
      },
    ];

    const { container } = render(<AssistantOperatorThread mode="dock" messages={messages} />);

    expect(container.querySelector('[data-slot="tool-fallback-result"]')).toBeInTheDocument();
    expect(screen.getByText(/"frames": 3/)).toBeInTheDocument();
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

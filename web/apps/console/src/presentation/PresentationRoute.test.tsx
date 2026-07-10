import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("../connection/api.js", () => ({
  callOperation: vi.fn().mockResolvedValue({
    ok: true,
    operation: "workflow.health",
    label: "Health",
    interpreted: { status: "ok" },
    exchange: { request: {}, response: {} },
    equivalentCli: "uv run wf status",
    durationMs: 2,
  }),
}));

class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
  globalThis.DOMRect = {
    fromRect: () => ({
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
      toJSON() {},
    }),
  } as unknown as typeof DOMRect;
});

const setReplayMode = () => {
  window.sessionStorage.setItem("lda.workflowConsole.target", "file:///invalid");
};

const graphNodeByLabel = (label: RegExp): HTMLElement => {
  const nodes = Array.from(document.querySelectorAll<HTMLElement>(".workflow-graph-stage__node"));
  const node = nodes.find((candidate) => label.test(candidate.getAttribute("aria-label") ?? ""));
  if (!node) throw new Error(`Could not find workflow graph node matching ${label}`);
  return node;
};

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  window.location.hash = "";
});

describe("PresentationRoute", () => {
  it("renders the presentation stage entry point", { timeout: 15000 }, async () => {
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(screen.getByRole("main", { name: /lda.chat presentation/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Design and Implementation of lda\.chat/i })).toBeInTheDocument();
  });

  it("starts from a scene hash and advances with keyboard", async () => {
    window.location.hash = "#scene/agent-handoff/request";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(screen.getByRole("heading", { name: /Agent Handoff/i })).toBeInTheDocument();
    await userEvent.keyboard("{ArrowRight}");
    expect(await screen.findByText(/The interface delegates durable work to lda\.chat/i)).toBeInTheDocument();
  });

  it("renders audience progress chrome without rail or mode label", async () => {
    setReplayMode();
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(screen.getByText(/replay evidence is active/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/presentation scene rail/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText("scene position")).toBeInTheDocument();
  });

  it("shows node spotlight when a graph node is selected", async () => {
    window.location.hash = "#scene/run-from-deployment/graph";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    fireEvent.click(graphNodeByLabel(/issue review/i));
    expect(screen.getByRole("dialog", { name: /issue review/i })).toBeInTheDocument();
    expect(screen.getByText("Workflow node")).toBeInTheDocument();
  });

  it("can advance replay far enough to show a product operation block", async () => {
    setReplayMode();
    window.location.hash = "#scene/run-from-deployment/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(await screen.findByLabelText("workflow.runs.start operation")).toBeInTheDocument();
  });

  it("opens a positioning branch via hash and returns to the parent scene first beat", async () => {
    window.location.hash = "#discuss/hosted-automation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(await screen.findByRole("button", { name: /return to positioning/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /return to positioning/i }));
    expect(window.location.hash).toBe("#scene/positioning/landscape");
  });

  it("uses the parent scene as return location for a directly linked branch", async () => {
    window.location.hash = "#discuss/mcp-agent-scale";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await userEvent.click(screen.getByRole("button", { name: /return to positioning/i }));
    expect(window.location.hash).toBe("#scene/positioning/landscape");
  });

  it("returns to the questions beat after closing a discussion opened from the index", async () => {
    const user = userEvent.setup();
    window.location.hash = "#scene/conclusion/questions";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    await user.click(screen.getByRole("button", { name: /where is the ai agent/i }));
    expect(window.location.hash).toBe("#discuss/where-is-ai-agent");

    await user.click(screen.getByRole("button", { name: /return to thesis/i }));
    expect(window.location.hash).toBe("#scene/conclusion/questions");
  });

  it("advances from the conclusion beat to the questions beat", async () => {
    window.location.hash = "#scene/conclusion/conclusion";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    await userEvent.keyboard("{ArrowRight}");

    expect(window.location.hash).toBe("#scene/conclusion/questions");
    expect(await screen.findByRole("navigation", { name: /defense discussion index/i })).toBeInTheDocument();
  });

  it("renders stable chat, primary, progress, and transient evidence surfaces", async () => {
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(screen.getByLabelText(/agent chat region/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/primary presentation region/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/presentation footer/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/evidence region/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });

  it("shows a receipt without auto-opening evidence on an evidence beat", async () => {
    window.location.hash = "#scene/resume-output-evidence/trace";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(await screen.findByRole("button", { name: /inspect evidence/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });

  it("opens the inspector from an explicit operation action", async () => {
    setReplayMode();
    const user = userEvent.setup();
    window.location.hash = "#scene/run-from-deployment/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await user.click(await screen.findByRole("button", { name: /view raw evidence/i }));
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
  });

  it("closes the inspector from the explicit close action", async () => {
    setReplayMode();
    const user = userEvent.setup();
    window.location.hash = "#scene/run-from-deployment/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await user.click(await screen.findByRole("button", { name: /view raw evidence/i }));
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /close evidence/i }));
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });

  it("returns to the receipt after closing the inspector on a receipt beat", async () => {
    setReplayMode();
    const user = userEvent.setup();
    window.location.hash = "#scene/resume-output-evidence/trace";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await user.click(await screen.findByRole("button", { name: /inspect evidence/i }));
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /close evidence/i }));
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /inspect evidence/i })).toBeInTheDocument();
  });

  it("renders a chat run action on the presentation route", async () => {
    window.location.hash = "#scene/agent-handoff/request";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("button", { name: /run prepared workflow|run replay walkthrough/i })).toBeInTheDocument();
  });

  it("uses stored target for live presentation mode", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("button", { name: /run prepared workflow/i })).toBeInTheDocument();
  });

  it("updates the chat intro after the live health probe succeeds", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("log", { name: "operator conversation" })).toBeInTheDocument();
    expect(await screen.findByText(/Live target is ready/i)).toBeInTheDocument();
    expect(screen.getByLabelText("presentation evidence mode")).toHaveAttribute("data-status", "ready");
    expect(screen.queryByText(/checking reachability/i)).not.toBeInTheDocument();
  });

  it("opens Scene 10 approval from the canonical hash", async () => {
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("heading", { name: /Typed Human Boundary/i })).toBeInTheDocument();
    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "approval");
  });

  it("renders replay-backed approval evidence on a direct approval hash", async () => {
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByText("Workflow input")).toBeInTheDocument();
    expect(screen.getByText("project-brief.md")).toBeInTheDocument();
    expect(screen.getByText("issue-board.json")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
    expect(screen.queryByText("Output not created yet")).not.toBeInTheDocument();
  });

  it("chat run action advances the replay timeline when no live server is configured", async () => {
    setReplayMode();
    window.location.hash = "#scene/run-from-deployment/operation";
    const user = userEvent.setup();
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const runButton = await screen.findByRole("button", { name: /run replay walkthrough/i });
    await user.click(runButton);
    expect(await screen.findByLabelText("workflow.runs.start operation")).toBeInTheDocument();
  });

  it("submits Scene 10 approval and advances to the resume beat", async () => {
    const user = userEvent.setup();
    setReplayMode();
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const submitButton = await screen.findByRole("button", { name: "Submit" });
    await waitFor(() => expect(submitButton).toBeEnabled(), { timeout: 10000 });

    await act(async () => {
      await user.click(submitButton);
    });

    expect(window.location.hash).toBe("#scene/resume-output-evidence/resume");
    expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  });

  it("reopens approval controls after returning from submitted resume", async () => {
    const user = userEvent.setup();
    setReplayMode();
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const submitButton = await screen.findByRole("button", { name: "Submit" });
    await waitFor(() => expect(submitButton).toBeEnabled(), { timeout: 10000 });
    await act(async () => {
      await user.click(submitButton);
    });
    expect(window.location.hash).toBe("#scene/resume-output-evidence/resume");

    window.location.hash = "#scene/typed-human-boundary/approval";
    window.dispatchEvent(new HashChangeEvent("hashchange"));

    expect(await screen.findByRole("button", { name: "Submit" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("cancels Scene 10 approval in replay without applying submitted evidence", async () => {
    const user = userEvent.setup();
    setReplayMode();
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const cancelButton = await screen.findByRole("button", { name: "Cancel" });
    await waitFor(() => expect(cancelButton).toBeEnabled(), { timeout: 10000 });

    await act(async () => {
      await user.click(cancelButton);
    });

    expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
    expect(window.location.hash).toBe("#scene/typed-human-boundary/approval");
    expect(screen.queryByLabelText("workflow.runs.resume operation")).not.toBeInTheDocument();
  });

  it("opens approval with enabled approval controls immediately after priming", async () => {
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("button", { name: "Submit" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("opens resume with resume operation proof immediately after priming", async () => {
    window.location.hash = "#scene/resume-output-evidence/resume";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  });

  it("direct approval route primes interrupt payload but not output", async () => {
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("region", { name: /interrupt report markdown/i })).toBeInTheDocument();
    expect(screen.queryByText("Output not created yet")).not.toBeInTheDocument();
  });

  it("direct resume route primes resume and output proof", async () => {
    window.location.hash = "#scene/resume-output-evidence/resume";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: /workflow markdown output/i })).toBeInTheDocument();
  });

  it.each([
    ["#scene/typed-human-boundary/approval", /Typed human boundary/i],
    ["#scene/resume-output-evidence/resume", /Resume, output, evidence/i],
    ["#scene/resume-output-evidence/trace", /Resume, output, evidence/i],
  ])("renders current demo hash %s without falling back to title", async (hash, heading) => {
    window.location.hash = hash;

    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Design and Implementation of lda\.chat/i })).not.toBeInTheDocument();
  });

  it("direct trace route primes trace frames", async () => {
    window.location.hash = "#scene/resume-output-evidence/trace";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("region", { name: /workflow trace frames/i })).toBeInTheDocument();
    expect(screen.queryByText("No trace frames captured.")).not.toBeInTheDocument();
  });

  it("navigates to Scene 8 request beat via hash", async () => {
    window.location.hash = "#scene/agent-handoff/request";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("heading", { name: "Agent Handoff" })).toBeInTheDocument();
    expect(screen.getByText(/A thin agent interface receives the report request/)).toBeInTheDocument();
  });

  it("navigates to Scene 8 handoff beat via hash", async () => {
    window.location.hash = "#scene/agent-handoff/handoff";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("heading", { name: "Agent Handoff" })).toBeInTheDocument();
    expect(screen.getByText(/The interface delegates durable work to lda\.chat/)).toBeInTheDocument();
  });

  it.each([
    "#scene/prepared-lifecycle/discover",
    "#scene/prepared-lifecycle/draft",
    "#scene/prepared-lifecycle/validate",
    "#scene/prepared-lifecycle/artifact",
    "#scene/prepared-lifecycle/deployment",
  ])("navigates to Scene 9 beat %s", async (hash) => {
    window.location.hash = hash;
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByLabelText("authoring phase rail")).toBeInTheDocument();
  });

  it("navigating Scene 9 beats does not call workflow authoring RPC operations", async () => {
    const { callOperation } = await import("../connection/api.js");
    const mockCallOp = vi.mocked(callOperation);
    mockCallOp.mockClear();
    window.location.hash = "#scene/prepared-lifecycle/draft";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByLabelText("authoring phase rail")).toBeInTheDocument();
    const authoringCalls = mockCallOp.mock.calls.filter((c) => c[0] !== "workflow.health");
    expect(authoringCalls).toHaveLength(0);
  });
});

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

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
    expect(screen.getByRole("heading", { name: /Thesis/ })).toBeInTheDocument();
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
    expect(screen.getByText(/replay fallback is active/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/presentation scene rail/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText("scene position")).toBeInTheDocument();
  });

  it("shows node spotlight when a graph node is selected", async () => {
    window.location.hash = "#scene/workflow-demo/graph";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await userEvent.click(screen.getByRole("button", { name: /issue review/i }));
    expect(screen.getByRole("dialog", { name: /issue review/i })).toBeInTheDocument();
    expect(screen.getByText("Workflow node")).toBeInTheDocument();
  });

  it("can advance replay far enough to show a product operation block", async () => {
    setReplayMode();
    window.location.hash = "#scene/workflow-demo/operation";
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
    window.location.hash = "#scene/interrupt-evidence/trace";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    expect(await screen.findByRole("button", { name: /inspect evidence/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: /evidence inspector/i })).not.toBeInTheDocument();
  });

  it("opens the inspector from an explicit operation action", async () => {
    setReplayMode();
    const user = userEvent.setup();
    window.location.hash = "#scene/workflow-demo/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await user.click(await screen.findByRole("button", { name: /view raw evidence/i }));
    expect(screen.getByRole("dialog", { name: /evidence inspector/i })).toBeInTheDocument();
  });

  it("closes the inspector from the explicit close action", async () => {
    setReplayMode();
    const user = userEvent.setup();
    window.location.hash = "#scene/workflow-demo/operation";
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
    window.location.hash = "#scene/interrupt-evidence/trace";
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

  it("opens Scene 10 approval from the canonical hash", async () => {
    window.location.hash = "#scene/interrupt-evidence/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("heading", { name: /Interrupt, Resume, Evidence/i })).toBeInTheDocument();
    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "approval");
  });

  it("renders replay-backed approval evidence on a direct approval hash", async () => {
    window.location.hash = "#scene/interrupt-evidence/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByLabelText("typed interrupt contract")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /issue review resume/i })).toBeInTheDocument();
    expect(screen.getByText(/Recorded resume payload for this decision/i)).toBeInTheDocument();
  });

  it("chat run action advances the replay timeline when no live server is configured", async () => {
    setReplayMode();
    window.location.hash = "#scene/workflow-demo/operation";
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
    window.location.hash = "#scene/interrupt-evidence/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const submitButton = await screen.findByRole("button", { name: "Submit" });
    await waitFor(() => expect(submitButton).toBeEnabled(), { timeout: 10000 });

    await act(async () => {
      await user.click(submitButton);
    });

    expect(window.location.hash).toBe("#scene/interrupt-evidence/resume");
    expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  });
});

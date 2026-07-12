import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { callOperation } from "../connection/api.js";

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

const mockedCallOperation = vi.mocked(callOperation);
const healthyResponse = {
  ok: true as const,
  operation: "workflow.health" as const,
  label: "Health",
  interpreted: { status: "ok" },
  exchange: { request: {}, response: {} },
  equivalentCli: "uv run wf status",
  durationMs: 2,
};

beforeAll(() => {
  mockedCallOperation.mockResolvedValue(healthyResponse);
});

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
  mockedCallOperation.mockReset();
  mockedCallOperation.mockResolvedValue(healthyResponse);
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
    expect(screen.getByRole("textbox", { name: /authoring request/i })).toBeInTheDocument();
    await userEvent.keyboard("{ArrowRight}");
    expect(await screen.findByLabelText("authoring phase rail")).toBeInTheDocument();
  });

  it("advances Draft to Validate once and projects the edited request", async () => {
    window.location.hash = "#scene/prepared-lifecycle/draft";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const message = screen.getByRole("textbox", { name: /message to authoring assistant/i });
    await userEvent.clear(message);
    await userEvent.type(message, "Check this edited draft request");
    await userEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(window.location.hash).toBe("#scene/prepared-lifecycle/validate");
    expect(await screen.findByText("Check this edited draft request")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i }))
      .toHaveAttribute("data-phase", "validate");
  });

  it("advances Artifact to Deployment once and projects the edited request", async () => {
    window.location.hash = "#scene/prepared-lifecycle/artifact";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const message = screen.getByRole("textbox", { name: /message to authoring assistant/i });
    await userEvent.clear(message);
    await userEvent.type(message, "Save this edited deployment request");
    await userEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(window.location.hash).toBe("#scene/prepared-lifecycle/deployment");
    expect(await screen.findByText("Save this edited deployment request")).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i }))
      .toHaveAttribute("data-phase", "deployment");
  });

  it("records a Deployment run request locally without an RPC", async () => {
    window.location.hash = "#scene/prepared-lifecycle/deployment";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);
    await screen.findByRole("textbox", { name: /message to authoring assistant/i });
    mockedCallOperation.mockClear();

    await userEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Run request prepared for the next execution slice.",
    );
    expect(mockedCallOperation.mock.calls.some(([operation]) => operation === "workflow.runs.start"))
      .toBe(false);
  });

  it("keeps Validate submission on the current beat", async () => {
    window.location.hash = "#scene/prepared-lifecycle/validate";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const message = screen.getByRole("textbox", { name: /message to authoring assistant/i });
    await userEvent.type(message, "Keep validating this draft");
    await userEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(window.location.hash).toBe("#scene/prepared-lifecycle/validate");
    expect(screen.getByRole("complementary", { name: /prepared authoring assistant/i }))
      .toHaveAttribute("data-phase", "validate");
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
    fireEvent.click(graphNodeByLabel(/review issues/i));
    expect(screen.getByRole("dialog", { name: /review issues/i })).toBeInTheDocument();
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

  it("renders the Scene 8 composer with one stable footer workflow action", async () => {
    window.location.hash = "#scene/agent-handoff/request";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("textbox", { name: /authoring request/i })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Run prepared workflow" })).toHaveLength(1);
  });

  it("backtracks across demo scenes without leaving stale footer chrome", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    window.location.hash = "#scene/agent-handoff/request";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("textbox", { name: /authoring request/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run prepared workflow" })).toBeInTheDocument();

    window.location.hash = "#scene/run-from-deployment/operation";
    fireEvent(window, new Event("hashchange"));
    expect(await screen.findByRole("button", { name: "Run prepared workflow" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "prepared workflow launch" })).not.toBeInTheDocument();

    window.location.hash = "#scene/run-from-deployment/graph";
    fireEvent(window, new Event("hashchange"));
    expect(await screen.findByRole("heading", { name: /Run From Deployment/i })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "prepared workflow launch" })).not.toBeInTheDocument();
    expect(screen.queryByText("Replay evidence")).not.toBeInTheDocument();

    window.location.hash = "#scene/thesis/title";
    fireEvent(window, new Event("hashchange"));
    expect(await screen.findByRole("heading", { name: /Design and Implementation of lda\.chat/i })).toBeInTheDocument();
    expect(screen.queryByLabelText("presentation evidence mode")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run prepared workflow" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry live service" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("presentation-demo-rail")).not.toBeInTheDocument();
  });

  it("removes the paused footer label after approval is submitted", async () => {
    setReplayMode();
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByText("Run paused - review required")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(screen.queryByText("Run paused - review required")).not.toBeInTheDocument();
  });

  it("uses stored target for live presentation mode", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    window.location.hash = "#scene/run-from-deployment/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findAllByRole("button", { name: /run prepared workflow/i })).toHaveLength(1);
  });

  it("owns the live run action in the footer rail", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    window.location.hash = "#scene/run-from-deployment/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const footer = await screen.findByRole("contentinfo", { name: /presentation footer/i });
    const runButton = within(footer).getByRole("button", { name: "Run prepared workflow" });
    expect(screen.queryByRole("region", { name: "prepared workflow launch" })).not.toBeInTheDocument();
    await userEvent.click(runButton);

    await waitFor(() => {
      expect(mockedCallOperation.mock.calls.some(([operation]) => operation === "workflow.deployments.inspect"))
        .toBe(true);
    }, { timeout: 3000 });
  });

  it("uses replay fallback for a live direct hash before a run starts", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByText(/Live target is ready/i)).toBeInTheDocument();
    expect(await screen.findByText("Workflow input")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Submit" })).toBeInTheDocument();
  });

  it("switches to replay evidence when a configured target fails health", async () => {
    mockedCallOperation.mockResolvedValue({
      ok: false as const,
      error: { code: "upstream_unreachable", message: "connection refused" },
      exchange: { request: {}, response: {} },
    });
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8766/rpc");
    window.location.hash = "#scene/resume-output-evidence/resume";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByText(/Replay fallback/i)).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: /workflow output report/i })).toBeInTheDocument();
  });

  it("updates the chat intro after the live health probe succeeds", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    window.location.hash = "#scene/run-from-deployment/operation";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("log", { name: "operator conversation" })).toBeInTheDocument();
    expect(await screen.findByText(/Live target is ready/i)).toBeInTheDocument();
    expect(screen.getByLabelText("presentation evidence mode")).toHaveAttribute("data-status", "ready");
    expect(screen.queryByText(/checking reachability/i)).not.toBeInTheDocument();
  });

  it("keeps Scene 8 local with a configured target", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    window.location.hash = "#scene/agent-handoff/request";
    mockedCallOperation.mockClear();
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByText(/Live target is ready/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
    expect(screen.getAllByRole("button", { name: "Run prepared workflow" })).toHaveLength(1);
    expect(mockedCallOperation).toHaveBeenCalledWith("workflow.health", "http://127.0.0.1:8765/rpc", {});
  });

  it("does not probe a configured target on the title route", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    mockedCallOperation.mockClear();
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(screen.getByRole("heading", { name: /Design and Implementation of lda\.chat/i })).toBeInTheDocument();
    expect(mockedCallOperation).not.toHaveBeenCalledWith("workflow.health", expect.anything(), expect.anything());
  });

  it("hides target status on a non-demo route", async () => {
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    window.location.hash = "#scene/conclusion/questions";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("contentinfo", { name: /presentation footer/i })).toBeInTheDocument();
    expect(screen.queryByLabelText("presentation evidence mode")).not.toBeInTheDocument();
  });

  it("opens Scene 10 approval from the canonical hash", async () => {
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("heading", { name: /Typed Human Boundary/i })).toBeInTheDocument();
    expect(screen.getByLabelText("demo workflow stage")).toHaveAttribute("data-demo-layout", "approval");
  });

  it("renders replay-backed approval evidence on a direct approval hash", async () => {
    setReplayMode();
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

    const footer = await screen.findByRole("contentinfo", { name: /presentation footer/i });
    const runButton = within(footer).getByRole("button", { name: /play replay walkthrough/i });
    expect(screen.queryByRole("region", { name: "prepared workflow launch" })).not.toBeInTheDocument();
    expect(screen.queryByText("Retry live service")).not.toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: "Request revision" })).toBeEnabled();
  });

  it("keeps a replay fallback on the revision-requested branch despite a configured live target", async () => {
    const user = userEvent.setup();
    window.sessionStorage.setItem("lda.workflowConsole.target", "http://127.0.0.1:8765/rpc");
    mockedCallOperation.mockRejectedValue(new Error("target unavailable"));
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const revisionButton = await screen.findByRole("button", { name: "Request revision" });
    await waitFor(() => expect(revisionButton).toBeEnabled(), { timeout: 10000 });

    await act(async () => {
      await user.click(revisionButton);
    });

    expect(window.location.hash).toBe("#scene/resume-output-evidence/resume");
    expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
    expect(screen.getByText(/Revision Requested/i)).toBeInTheDocument();

    window.location.hash = "#scene/resume-output-evidence/trace";
    window.dispatchEvent(new HashChangeEvent("hashchange"));

    expect(await screen.findByText("revision_requested")).toBeInTheDocument();
    expect(screen.getByText("end_cancelled")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "workflow output summary" })).toBeInTheDocument();
  });

  it("opens approval with enabled approval controls immediately after priming", async () => {
    setReplayMode();
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("button", { name: "Submit" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Request revision" })).toBeEnabled();
  });

  it("opens resume with resume operation proof immediately after priming", async () => {
    setReplayMode();
    window.location.hash = "#scene/resume-output-evidence/resume";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  });

  it("direct approval route primes interrupt payload but not output", async () => {
    setReplayMode();
    window.location.hash = "#scene/typed-human-boundary/approval";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("region", { name: /interrupt report markdown/i })).toBeInTheDocument();
    expect(screen.queryByText("Output not created yet")).not.toBeInTheDocument();
  });

  it("direct resume route primes resume and output proof", async () => {
    setReplayMode();
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
    setReplayMode();
    window.location.hash = "#scene/resume-output-evidence/trace";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("region", { name: /workflow trace frames/i })).toBeInTheDocument();
    expect(screen.queryByText("No trace frames captured.")).not.toBeInTheDocument();
    expect(screen.getByText("list_documents")).toBeInTheDocument();
    expect(screen.getByText("review_issues")).toBeInTheDocument();
    expect(screen.getByText("finalise_report")).toBeInTheDocument();
  });

  it("keeps trace frames when navigating from output to trace", async () => {
    setReplayMode();
    window.location.hash = "#scene/resume-output-evidence/output";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    expect(await screen.findByRole("region", { name: /workflow output report/i })).toBeInTheDocument();
    window.location.hash = "#scene/resume-output-evidence/trace";
    fireEvent(window, new Event("hashchange"));

    expect(await screen.findByText("finalise_report")).toBeInTheDocument();
    expect(screen.queryByText("No trace frames captured.")).not.toBeInTheDocument();
  });

  it("navigates to Scene 8 request beat via hash", async () => {
    window.location.hash = "#scene/agent-handoff/request";
    const { PresentationRoute } = await import("./PresentationRoute.js");
    render(<PresentationRoute />);

    const send = await screen.findByRole("button", { name: "Send" });
    await userEvent.click(send);
    expect(await screen.findByRole("log", { name: "prepared authoring conversation" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /discover.*4 tool calls/i })).toBeInTheDocument();
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

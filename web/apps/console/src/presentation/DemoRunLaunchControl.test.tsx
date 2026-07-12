import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import type { TimelineAgentController, TimelineAgentMode } from "../demo/agent/timelineAgent.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import type { PresentationTargetHealth } from "./presentation-target-status.js";
import { DemoRunLaunchControl } from "./DemoRunLaunchControl.js";

const target = "http://127.0.0.1:8765/rpc";

const demoController = (
  phase: DemoTimelineController["state"]["phase"] = "ready",
): DemoTimelineController => ({
  state: { ...initialDemoTimelineState, phase },
  inFlight: false,
  interruptPayload: null,
  output: null,
  trace: null,
  missingDeploymentMessage: null,
  recordingId: null,
  canStart: true,
  setMode: vi.fn(),
  start: vi.fn(),
  pause: vi.fn(),
  play: vi.fn(),
  next: vi.fn(async () => {}),
  submitSelectedIssues: vi.fn(async () => {}),
  requestRevision: vi.fn(async () => {}),
  restart: vi.fn(),
  primeReplayToStage: vi.fn(),
});

const timelineAgent = (
  runPreparedWorkflow: (mode?: TimelineAgentMode) => Promise<void>,
  overrides: Partial<TimelineAgentController> = {},
): TimelineAgentController => ({
  messages: [],
  canRun: true,
  canRunLive: true,
  runLabel: "Run prepared workflow",
  runPreparedWorkflow,
  submitSelectedIssues: vi.fn(async () => {}),
  requestRevision: vi.fn(async () => {}),
  ...overrides,
});

const readyStatus: PresentationTargetHealth = {
  kind: "ready",
  target,
  label: "Live target ready",
  detail: "127.0.0.1:8765",
};

const replayStatus: PresentationTargetHealth = {
  kind: "replay",
  label: "Replay evidence",
  detail: "reviewed recording",
};

const failedStatus: PresentationTargetHealth = {
  kind: "failed",
  target,
  label: "Replay fallback",
  detail: "connection refused",
};

const checkingStatus: PresentationTargetHealth = {
  kind: "checking",
  target,
  label: "Live target configured",
  detail: "checking",
};

const renderControl = (options: {
  readonly status?: PresentationTargetHealth;
  readonly liveTargetReady?: boolean;
  readonly demo?: DemoTimelineController;
  readonly agent?: TimelineAgentController;
} = {}) => render(
  <DemoRunLaunchControl
    status={options.status ?? readyStatus}
    liveTargetReady={options.liveTargetReady ?? true}
    demo={options.demo ?? demoController()}
    timelineAgent={options.agent ?? timelineAgent(async () => {})}
    retryHealth={vi.fn()}
  />,
);

afterEach(() => cleanup());

describe("DemoRunLaunchControl", () => {
  it("launches live from a healthy target", async () => {
    const run = vi.fn(async () => {});
    renderControl({ agent: timelineAgent(run) });

    await userEvent.click(screen.getByRole("button", { name: "Run prepared workflow" }));

    expect(run).toHaveBeenCalledWith("live");
  });

  it("keeps the live action available from a direct replay view", async () => {
    const run = vi.fn(async () => {});
    renderControl({
      status: replayStatus,
      liveTargetReady: true,
      agent: timelineAgent(run),
    });

    expect(screen.getByText("Live target ready")).toBeInTheDocument();
    expect(screen.getByText("Direct view is replay; launch starts live operations.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run prepared workflow" }));

    expect(run).toHaveBeenCalledWith("live");
  });

  it("offers explicit replay and retry after health failure", async () => {
    const run = vi.fn(async () => {});
    const retry = vi.fn();
    render(
      <DemoRunLaunchControl
        status={failedStatus}
        liveTargetReady={false}
        demo={demoController()}
        timelineAgent={timelineAgent(run)}
        retryHealth={retry}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Play replay walkthrough" }));
    await userEvent.click(screen.getByRole("button", { name: "Retry live service" }));

    expect(run).toHaveBeenCalledWith("replay");
    expect(retry).toHaveBeenCalledOnce();
  });

  it("does not offer retry when no live target is configured", () => {
    renderControl({ status: replayStatus, liveTargetReady: false });

    expect(screen.getByRole("button", { name: "Play replay walkthrough" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry live service" })).not.toBeInTheDocument();
  });

  it("keeps the action visible but disabled while health is checking", () => {
    renderControl({ status: checkingStatus, liveTargetReady: false });

    expect(screen.getByRole("button", { name: "Checking live service" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Retry live service" })).toBeDisabled();
  });

  it("disables duplicate starts while the live timeline is running", () => {
    renderControl({ status: { ...readyStatus, kind: "active", label: "Live run active", detail: "operations sent" }, demo: demoController("running") });

    expect(screen.getByRole("button", { name: "Live workflow running" })).toBeDisabled();
  });
});

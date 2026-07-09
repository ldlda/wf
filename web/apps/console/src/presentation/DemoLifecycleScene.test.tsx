import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { DemoLifecycleScene } from "./DemoLifecycleScene.js";
import { findBeat, findScene } from "./storyboard.js";

const recording = loadCanonicalDemoRecording();
const demo: DemoTimelineController = {
  state: {
    ...initialDemoTimelineState,
    mode: "replay",
    phase: "paused",
    events: recording.events,
    appliedCount: recording.events.length,
    autoplay: false,
  },
  inFlight: false,
  interruptPayload: null,
  output: null,
  trace: null,
  missingDeploymentMessage: null,
  recordingId: recording.recordingId,
  canStart: true,
  setMode: vi.fn(),
  start: vi.fn(),
  pause: vi.fn(),
  play: vi.fn(),
  next: vi.fn(async () => {}),
  submitSelectedIssues: vi.fn(async () => {}),
  cancelReview: vi.fn(async () => {}),
  restart: vi.fn(),
  primeReplayToStage: vi.fn(),
};

const renderBeat = (beatId: "draft" | "artifact" | "deployment" | "ready-run") => {
  const scene = findScene("prepared-lifecycle");
  const beat = findBeat("prepared-lifecycle", beatId);
  if (!scene || !beat) throw new Error(`missing prepared-lifecycle/${beatId}`);
  render(<DemoLifecycleScene scene={scene} beat={beat} demo={demo} />);
};

describe("DemoLifecycleScene", () => {
  it("renders prepared draft context honestly", () => {
    renderBeat("draft");
    expect(screen.getByRole("region", { name: "prepared workflow lifecycle" })).toHaveAttribute("data-active-lifecycle", "draft");
    expect(screen.getByText("prepared context")).toBeInTheDocument();
    expect(screen.getByText("examples/lda_report_workflow")).toBeInTheDocument();
  });

  it("renders artifact and deployment facts from replay evidence", () => {
    renderBeat("deployment");
    expect(screen.getByText("lda_report_case_study.default")).toBeInTheDocument();
    expect(screen.getByText("block")).toBeInTheDocument();
    expect(screen.getByText(/local\.lda_docs/)).toBeInTheDocument();
  });

  it("renders run readiness without claiming output exists yet", () => {
    renderBeat("ready-run");
    expect(screen.getByText("run_recorded_lda_report")).toBeInTheDocument();
    expect(screen.getByText("interrupted")).toBeInTheDocument();
    expect(screen.queryByText(/created issues/i)).not.toBeInTheDocument();
  });
});

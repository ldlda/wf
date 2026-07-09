import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { projectInterruptContract, projectOperationPresentation } from "./demo-workflow-model.js";
import { GuidedProductMoment } from "./GuidedProductMoment.js";
import { findBeat } from "./storyboard.js";

afterEach(() => cleanup());

const recording = loadCanonicalDemoRecording();
const runStart = recording.events.find((event) => event.stage === "run_start")!;
const runResume = recording.events.find((event) => event.stage === "run_resume")!;
const contract = projectInterruptContract(runStart, runResume);
const resumeOperation = projectOperationPresentation(runResume);
const demo = {
  state: { mode: "replay", phase: "review", events: recording.events, appliedCount: 3, autoplay: false, error: null },
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
  next: vi.fn(),
  submitSelectedIssues: vi.fn(),
  cancelReview: vi.fn(),
  restart: vi.fn(),
  primeReplayToStage: vi.fn(),
} as unknown as DemoTimelineController;

describe("GuidedProductMoment", () => {
  it("makes approval the primary product decision", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("interrupt-evidence", "approval")!}
        demo={demo}
        contract={contract}
        operation={null}
        approvalActions={{
          state: "ready",
          canSubmit: true,
          canCancel: true,
          submit: vi.fn(async () => {}),
          cancel: vi.fn(async () => {}),
        }}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "approval");
    expect(screen.getByText(/Run is paused/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

  it("makes resume operation proof primary on resume beat", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("interrupt-evidence", "resume")!}
        demo={demo}
        contract={contract}
        operation={resumeOperation}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "resume");
    expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  });

  it("marks the primary surface for visual hierarchy", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("interrupt-evidence", "approval")!}
        demo={demo}
        contract={contract}
        operation={null}
        approvalActions={{
          state: "ready",
          canSubmit: true,
          canCancel: true,
          submit: vi.fn(async () => {}),
          cancel: vi.fn(async () => {}),
        }}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveClass("guided-product-moment");
    expect(screen.getByLabelText("typed interrupt contract")).toHaveAttribute("data-hero", "true");
  });
});

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
  interruptPayload: {
    report_markdown: "# lda.chat Thesis And Project Readiness Report\n\nThe workflow substrate is ready for the defense demo.",
    proposed_issues: [
      {
        id: "risk-1",
        title: "Prepare the defense walkthrough",
        body: "Review the live and replay paths before the defense.",
        severity: "medium",
      },
    ],
  },
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
  it("makes approval the primary product decision with factual panels", () => {
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
    expect(screen.getByText("Workflow input")).toBeInTheDocument();
    expect(screen.getByText("project-brief.md")).toBeInTheDocument();
    expect(screen.getByText("issue-board.json")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
    expect(screen.queryByText("Output not created yet")).not.toBeInTheDocument();
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
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
  });
});

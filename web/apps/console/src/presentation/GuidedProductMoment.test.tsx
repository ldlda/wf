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

const demoWithAppliedCount = (appliedCount: number): DemoTimelineController => ({
  ...demo,
  state: {
    ...demo.state,
    appliedCount,
    phase: "completed",
  },
});

describe("GuidedProductMoment", () => {
  it("makes approval the primary product decision with factual panels", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("typed-human-boundary", "approval")!}
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
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-primary-surface", "interrupt-approval");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-approval-focus", "decision");
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
        beat={findBeat("resume-output-evidence", "resume")!}
        demo={demo}
        contract={contract}
        operation={resumeOperation}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-moment", "resume");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-primary-surface", "resume-output");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-continuation-focus", "output");
    expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
  });

  it("keeps approval focused on input and decision without pre-resume output", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("typed-human-boundary", "approval")!}
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

    expect(screen.getByText("Workflow input")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /operator resume decision/i })).toBeInTheDocument();
    expect(screen.queryByText("Output not created yet")).not.toBeInTheDocument();
    expect(screen.getAllByText(/lda.chat Thesis And Project Readiness Report/i).length).toBeGreaterThanOrEqual(1);
  });

  it("marks the primary surface for visual hierarchy", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("typed-human-boundary", "approval")!}
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

  it("approval uses a compact input rail and a dominant interrupt report", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("typed-human-boundary", "approval")!}
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

    expect(screen.getByRole("region", { name: /workflow input summary/i })).toHaveAttribute("data-density", "compact");
    expect(screen.getByRole("region", { name: /interrupt report and proposed issues/i })).toHaveAttribute("data-priority", "primary");
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
    expect(screen.queryByText("Output")).not.toBeInTheDocument();
  });

  it("approval shows input, interrupt payload, and decision but no output or trace", () => {
    render(
      <GuidedProductMoment
        beat={findBeat("typed-human-boundary", "approval")!}
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

    expect(screen.getByText("Workflow input")).toBeInTheDocument();
    expect(screen.getByText("Interrupt payload")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /interrupt report markdown/i })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /operator resume decision/i })).toBeInTheDocument();
    expect(screen.queryByText("Output")).not.toBeInTheDocument();
    expect(screen.queryByText("Trace frames")).not.toBeInTheDocument();
    expect(document.querySelector(".interrupt-decision-form__report-preview")).toBeNull();
  });

  it("resume makes output primary and operation/resume payload supporting", () => {
    const resumedDemo = demoWithAppliedCount(6);

    render(
      <GuidedProductMoment
        beat={findBeat("resume-output-evidence", "resume")!}
        demo={resumedDemo}
        contract={contract}
        operation={resumeOperation}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /resume proof support/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /workflow output report/i })).toHaveAttribute("data-output-priority", "report");
    expect(screen.getByRole("region", { name: /workflow markdown output/i })).toBeInTheDocument();
  });

  it("resume shows operation, resume payload, and large output report", () => {
    const resumedDemo = demoWithAppliedCount(6);

    render(
      <GuidedProductMoment
        beat={findBeat("resume-output-evidence", "resume")!}
        demo={resumedDemo}
        contract={contract}
        operation={resumeOperation}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("workflow.runs.resume operation")).toBeInTheDocument();
    expect(screen.getByText("Resume decision")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /workflow markdown output/i })).toBeInTheDocument();
  });

  it("output beat makes the report and created issues primary", () => {
    const resumedDemo = demoWithAppliedCount(6);

    render(
      <GuidedProductMoment
        beat={findBeat("resume-output-evidence", "output")!}
        demo={resumedDemo}
        contract={contract}
        operation={null}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /workflow markdown output/i })).toHaveClass("run-facts-scroll-region");
    expect(screen.getByText("ISSUE-001")).toBeInTheDocument();
  });

  it("trace makes trace frames primary with compact output support", () => {
    const tracedDemo = demoWithAppliedCount(5);

    render(
      <GuidedProductMoment
        beat={findBeat("resume-output-evidence", "trace")!}
        demo={tracedDemo}
        contract={contract}
        operation={null}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-support-surface", "output-summary");
    expect(screen.getByRole("region", { name: /current product moment/i })).toHaveAttribute("data-continuation-focus", "trace");
    expect(screen.getByRole("region", { name: /workflow trace proof/i })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /workflow output summary/i })).toHaveAttribute("data-output-priority", "summary");
    expect(screen.queryByText("No trace frames captured.")).not.toBeInTheDocument();
    expect(document.querySelectorAll(".run-trace-frame")).toHaveLength(3);
  });

  it("trace beat shows trace frames instead of the empty fallback after trace is primed", () => {
    const tracedDemo = demoWithAppliedCount(5);

    render(
      <GuidedProductMoment
        beat={findBeat("resume-output-evidence", "trace")!}
        demo={tracedDemo}
        contract={contract}
        operation={null}
        openEvidence={vi.fn()}
      />,
    );

    expect(screen.queryByText("No trace frames captured.")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: /workflow trace frames/i })).toBeInTheDocument();
  });
});

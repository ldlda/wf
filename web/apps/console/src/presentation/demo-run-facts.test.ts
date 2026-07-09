import { describe, expect, it, vi } from "vitest";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { formatFactValue, projectDemoRunFacts } from "./demo-run-facts.js";

const controller = (overrides: Partial<DemoTimelineController> = {}): DemoTimelineController => {
  const recording = loadCanonicalDemoRecording();
  return {
    state: {
      ...initialDemoTimelineState,
      mode: "replay",
      phase: "review",
      events: recording.events,
      appliedCount: 3,
      autoplay: false,
    },
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
    recordingId: "lda-report-success-v1",
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
    ...overrides,
  };
};

describe("demo-run-facts", () => {
  it("projects workflow input from run_start params", () => {
    const facts = projectDemoRunFacts(controller());

    expect(facts.input.selectedDocuments).toEqual([
      "project-brief.md",
      "architecture-notes.md",
      "evaluation-findings.md",
      "risk-register.md",
      "roadmap.md",
    ]);
    expect(facts.input.boardPath).toBe("issue-board.json");
  });

  it("projects interrupt payload and state", () => {
    const facts = projectDemoRunFacts(controller());

    expect(facts.interrupt.kind).toBe("issue_review");
    expect(facts.interrupt.typed).toBe(true);
    expect(facts.interrupt.outcomes).toEqual(["submitted", "cancelled"]);
    expect(facts.interrupt.proposedIssues[0]).toMatchObject({
      id: "risk-1",
      title: "Prepare the defense walkthrough",
      severity: "medium",
    });
    expect(facts.interrupt.reportMarkdownPreview).toContain("workflow substrate is ready");
  });

  it("projects interrupt payload from recorded events when transient state is absent", () => {
    const facts = projectDemoRunFacts(controller({ interruptPayload: null }));

    expect(facts.interrupt.proposedIssues[0]).toMatchObject({
      id: "risk-1",
      title: "Prepare the defense walkthrough",
    });
    expect(facts.interrupt.reportMarkdownPreview).toContain("workflow substrate is ready");
  });

  it("projects resume payload and output after resume", () => {
    const recording = loadCanonicalDemoRecording();
    const facts = projectDemoRunFacts(controller({
      state: {
        ...initialDemoTimelineState,
        mode: "replay",
        phase: "completed",
        events: recording.events,
        appliedCount: 6,
        autoplay: false,
      },
    }));

    expect(facts.resume.outcome).toBe("submitted");
    expect(facts.resume.payload).toMatchObject({
      approved: true,
      selected_issue_ids: ["risk-1"],
      comment: "Create the selected issue.",
    });
    expect(facts.output.state).toBe("created");
    if (facts.output.state === "created") {
      expect(facts.output.createdIssues[0]).toMatchObject({ id: "ISSUE-001" });
    }
  });

  it("marks output as not created before resume", () => {
    const facts = projectDemoRunFacts(controller());
    expect(facts.output.state).toBe("not-created");
    if (facts.output.state === "not-created") {
      expect(facts.output.message).toBe("Output not created yet");
    }
  });

  it("projects trace frames and empty object state accurately", () => {
    const recording = loadCanonicalDemoRecording();
    const facts = projectDemoRunFacts(controller({
      state: {
        ...initialDemoTimelineState,
        mode: "replay",
        phase: "completed",
        events: recording.events,
        appliedCount: 6,
        autoplay: false,
      },
    }));

    expect(facts.trace.frames).toHaveLength(3);
    expect(facts.trace.frames[0]).toMatchObject({
      nodeId: "list_documents",
      resolvedInputLabel: "captured as empty object",
      outputLabel: "captured as empty object",
      stateChangesLabel: "captured as empty object",
    });
  });

  it("formats absent and empty values differently", () => {
    expect(formatFactValue({}, "not captured in this recording")).toBe("captured as empty object");
    expect(formatFactValue(undefined, "not captured in this recording")).toBe("not captured in this recording");
  });
});

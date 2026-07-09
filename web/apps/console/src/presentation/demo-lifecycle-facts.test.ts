import { describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording } from "../demo/timeline/replay.js";
import { initialDemoTimelineState } from "../demo/timeline/reducer.js";
import type { DemoTimelineController } from "../demo/useDemoTimeline.js";
import { projectDemoLifecycleFacts } from "./demo-lifecycle-facts.js";

const controller = (eventMode: "recorded" | "empty" = "recorded"): DemoTimelineController => {
  const recording = loadCanonicalDemoRecording();
  return {
    state: {
      ...initialDemoTimelineState,
      mode: "replay",
      phase: "paused",
      events: eventMode === "recorded" ? recording.events : [],
      appliedCount: eventMode === "recorded" ? recording.events.length : 0,
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
};

describe("projectDemoLifecycleFacts", () => {
  it("projects prepared draft context without pretending it was runtime evidence", () => {
    const facts = projectDemoLifecycleFacts(controller());
    expect(facts.draft.label).toBe("lda report workflow");
    expect(facts.draft.source).toContain("examples/lda_report_workflow");
    expect(facts.draft.status).toBe("prepared context");
  });

  it("projects artifact and deployment facts from deployment inspect evidence", () => {
    const facts = projectDemoLifecycleFacts(controller());
    expect(facts.artifact).toEqual({ id: "lda_report_case_study", version: 1 });
    expect(facts.deployment.id).toBe("lda_report_case_study.default");
    expect(facts.deployment.driftPolicy).toBe("block");
    expect(facts.deployment.bindings).toContainEqual(["local.lda_docs", "local.lda_docs"]);
  });

  it("projects run readiness from the run start event", () => {
    const facts = projectDemoLifecycleFacts(controller());
    expect(facts.run.id).toBe("run_recorded_lda_report");
    expect(facts.run.status).toBe("interrupted");
  });

  it("falls back honestly when replay evidence has not loaded yet", () => {
    const facts = projectDemoLifecycleFacts(controller("empty"));

    expect(facts.artifact).toEqual({ id: "unavailable", version: null });
    expect(facts.deployment).toEqual({
      id: "unavailable",
      driftPolicy: "unavailable",
      bindings: [],
    });
    expect(facts.run).toEqual({ id: null, status: "not started" });
  });
});

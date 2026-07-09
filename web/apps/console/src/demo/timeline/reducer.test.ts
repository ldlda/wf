import { describe, expect, it } from "vitest";
import {
  demoTimelineReducer,
  initialDemoTimelineState,
  currentDemoEvent,
} from "./reducer.js";
import type { DemoEvent } from "./models.js";

const event = (sequence: number, stage: DemoEvent["stage"]): DemoEvent => ({
  id: `event-${sequence}`,
  sequence,
  stage,
  operation: stage === "interrupt" || stage === "completed" ? null : "workflow.runs.start",
  reason: `Apply ${stage}`,
  equivalentCli: null,
  params: {},
  rawResponse: {},
  interpreted: {},
  durationMs: 1,
  resultingIds: {
    deploymentId: "lda_report_case_study.default",
    runId: sequence > 0 ? "run_demo" : null,
  },
  recordedAt: "2026-07-03T00:00:00.000Z",
});

describe("demoTimelineReducer", () => {
  it("starts live playback in running phase", () => {
    const state = demoTimelineReducer(initialDemoTimelineState, {
      type: "start",
      mode: "live",
      events: [],
    });
    expect(state.phase).toBe("running");
    expect(state.autoplay).toBe(true);
    expect(state.appliedCount).toBe(0);
  });

  it("applies events in order", () => {
    const started = demoTimelineReducer(initialDemoTimelineState, {
      type: "start",
      mode: "replay",
      events: [event(0, "deployment_check"), event(1, "run_start")],
    });
    const applied = demoTimelineReducer(started, { type: "apply_next" });
    expect(applied.appliedCount).toBe(1);
    expect(currentDemoEvent(applied)?.stage).toBe("deployment_check");
  });

  it("always pauses at an interrupt", () => {
    const started = demoTimelineReducer(initialDemoTimelineState, {
      type: "start",
      mode: "replay",
      events: [event(0, "interrupt")],
    });
    const applied = demoTimelineReducer(started, { type: "apply_next" });
    expect(applied.phase).toBe("review");
    expect(applied.autoplay).toBe(false);
  });

  it("stops at completion and failure", () => {
    for (const stage of ["completed", "failed"] as const) {
      const started = demoTimelineReducer(initialDemoTimelineState, {
        type: "start",
        mode: "replay",
        events: [event(0, stage)],
      });
      const applied = demoTimelineReducer(started, { type: "apply_next" });
      expect(applied.phase).toBe(stage);
      expect(applied.autoplay).toBe(false);
    }
  });

  it("pause and play preserve playback position", () => {
    const started = demoTimelineReducer(initialDemoTimelineState, {
      type: "start",
      mode: "replay",
      events: [event(0, "deployment_check")],
    });
    const paused = demoTimelineReducer(started, { type: "pause" });
    const resumed = demoTimelineReducer(paused, { type: "play" });
    expect(paused.phase).toBe("paused");
    expect(resumed.phase).toBe("running");
    expect(resumed.appliedCount).toBe(0);
  });

  it("keeps manual playback paused after applying one ordinary event", () => {
    const started = demoTimelineReducer(initialDemoTimelineState, {
      type: "start",
      mode: "replay",
      events: [event(0, "deployment_check")],
    });
    const paused = demoTimelineReducer(started, { type: "pause" });
    const applied = demoTimelineReducer(paused, { type: "apply_next" });

    expect(applied.phase).toBe("paused");
    expect(applied.appliedCount).toBe(1);
    expect(applied.autoplay).toBe(false);
  });

  it("restart clears transient playback without deleting mode", () => {
    const started = demoTimelineReducer(initialDemoTimelineState, {
      type: "start",
      mode: "replay",
      events: [event(0, "completed")],
    });
    const restarted = demoTimelineReducer(started, { type: "restart" });
    expect(restarted.phase).toBe("ready");
    expect(restarted.mode).toBe("replay");
    expect(restarted.appliedCount).toBe(0);
  });

  it("cancels review as a terminal non-autoplay phase", () => {
    const reviewing = {
      ...initialDemoTimelineState,
      mode: "replay" as const,
      phase: "review" as const,
      events: [event(0, "interrupt")],
      appliedCount: 1,
      autoplay: false,
    };
    const cancelled = demoTimelineReducer(reviewing, { type: "cancel_review" });

    expect(cancelled.phase).toBe("cancelled");
    expect(cancelled.autoplay).toBe(false);
    expect(cancelled.appliedCount).toBe(1);
  });
});

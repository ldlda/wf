import { describe, expect, it } from "vitest";
import {
  DEMO_CHROME_SCENE_IDS,
  demoChromeFor,
  isDemoChromeScene,
  type DemoChromeInput,
} from "./presentation-demo-chrome.js";

const replayStatus = {
  kind: "replay",
  label: "Replay evidence",
  detail: "reviewed recording",
} as const;

const checkingStatus = {
  kind: "checking",
  target: "http://127.0.0.1:8765/rpc",
  label: "Live target configured",
  detail: "checking",
} as const;

const failedStatus = {
  kind: "failed",
  target: "http://127.0.0.1:8765/rpc",
  label: "Replay fallback",
  detail: "connection refused",
} as const;

const baseInput: DemoChromeInput = {
  sceneId: "agent-handoff",
  phase: "ready",
  mode: "replay",
  inFlight: false,
  approvalState: "ready",
  targetStatus: replayStatus,
  liveTargetReady: false,
  canRun: true,
  canRunLive: false,
};

describe("isDemoChromeScene", () => {
  it("includes every demo scene and excludes the surrounding presentation scenes", () => {
    expect(DEMO_CHROME_SCENE_IDS).toEqual([
      "agent-handoff",
      "prepared-lifecycle",
      "run-from-deployment",
      "typed-human-boundary",
      "resume-output-evidence",
    ]);

    for (const sceneId of DEMO_CHROME_SCENE_IDS) {
      expect(isDemoChromeScene(sceneId)).toBe(true);
    }

    for (const sceneId of ["thesis", "architecture", "authoring", "evaluation", "conclusion"] as const) {
      expect(isDemoChromeScene(sceneId)).toBe(false);
    }
  });
});

describe("demoChromeFor", () => {
  it("hides chrome outside the demo scenes", () => {
    expect(demoChromeFor({ ...baseInput, sceneId: "thesis" }).kind).toBe("hidden");
  });

  it("shows an action for a ready demo scene", () => {
    expect(demoChromeFor({ ...baseInput, sceneId: "agent-handoff" }).kind).toBe("action");
  });

  it("shows checking before exposing an action", () => {
    expect(demoChromeFor({ ...baseInput, targetStatus: checkingStatus }).kind).toBe("checking");
  });

  it("shows a live run while the live timeline is active", () => {
    expect(demoChromeFor({ ...baseInput, mode: "live", phase: "running", inFlight: true }).kind).toBe("running");
  });

  it("pauses at the typed human boundary for a ready decision", () => {
    expect(demoChromeFor({ ...baseInput, sceneId: "typed-human-boundary", phase: "review" }).kind).toBe("paused");
  });

  it("resumes immediately after a decision is submitted", () => {
    expect(demoChromeFor({
      ...baseInput,
      sceneId: "typed-human-boundary",
      phase: "review",
      approvalState: "submitted",
    }).kind).toBe("resuming");
  });

  it("shows completion before any other run state", () => {
    expect(demoChromeFor({ ...baseInput, phase: "completed" }).kind).toBe("completed");
  });

  it("falls back to the replay action when the live target is unavailable", () => {
    const fallback = demoChromeFor({ ...baseInput, liveTargetReady: false, targetStatus: failedStatus });
    expect(fallback.kind).toBe("action");
    if (fallback.kind === "action") expect(fallback.label).toBe("Play replay walkthrough");
  });

  it("projects the selected timeline capability and retry state", () => {
    const liveAction = demoChromeFor({
      ...baseInput,
      mode: "live",
      targetStatus: { ...failedStatus, kind: "ready" },
      liveTargetReady: true,
      canRunLive: true,
      canRun: false,
    });

    expect(liveAction).toMatchObject({
      kind: "action",
      mode: "live",
      label: "Run prepared workflow",
      canRun: true,
      canRetry: true,
    });
  });
});

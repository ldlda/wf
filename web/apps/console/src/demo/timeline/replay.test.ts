import { describe, expect, it, vi } from "vitest";
import { loadCanonicalDemoRecording, nextReplayEvent } from "./replay.js";

vi.mock("../../connection/api.js", () => ({
  callOperation: vi.fn(() => {
    throw new Error("replay must not call RPC");
  }),
}));

describe("canonical demo recording", () => {
  it("loads a complete reviewed recording", () => {
    const recording = loadCanonicalDemoRecording();
    expect(recording.schemaVersion).toBe(1);
    expect(recording.deploymentId).toBe("lda_report_case_study.default");
    expect(recording.events.map((event) => event.stage)).toEqual([
      "deployment_check",
      "run_start",
      "interrupt",
      "run_resume",
      "trace_read",
      "completed",
    ]);
  });

  it("returns one replay event by applied count", () => {
    const recording = loadCanonicalDemoRecording();
    expect(nextReplayEvent(recording, 0)?.stage).toBe("deployment_check");
    expect(nextReplayEvent(recording, recording.events.length)).toBeNull();
  });
});

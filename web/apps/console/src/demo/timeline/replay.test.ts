import { describe, expect, it, vi } from "vitest";
import {
  loadCanonicalDemoRecording,
  nextReplayEvent,
  revisionReplayRecording,
} from "./replay.js";

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

  it("projects a truthful revision-requested branch", () => {
    const recording = revisionReplayRecording(loadCanonicalDemoRecording());
    const resume = recording.events.find((event) => event.stage === "run_resume");
    const completed = recording.events.find((event) => event.stage === "completed");

    expect(recording.recordingId).toBe("lda-report-revision-v1");
    expect(resume?.params).toMatchObject({
      resume_outcome: "cancelled",
      resume_payload: { approved: false, selected_issue_ids: [] },
    });
    expect((resume?.interpreted as { output: { approved: boolean; created_issues: unknown[] } }).output).toEqual({
      approved: false,
      markdown: "# Revision Requested\n\nRequest revisions before creating issues.",
      created_issues: [],
      selected_issue_ids: [],
      comment: "Request revisions before creating issues.",
    });
    expect((completed?.interpreted as { trace: { frames: unknown[] } }).trace.frames).toHaveLength(9);
  });
});

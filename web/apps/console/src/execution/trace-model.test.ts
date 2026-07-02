import { describe, it, expect } from "vitest";
import { buildTraceFrames, type TraceFrameView } from "./trace-model.js";

const sampleTracePage = {
  frames: [
    {
      nodeId: "start",
      stepType: "use",
      resolvedInput: {},
      outcome: "ok",
      output: { report_id: "rpt_1" },
      stateChanges: {},
    },
    {
      nodeId: "review",
      stepType: "interrupt",
      resolvedInput: { report: "..." },
      outcome: "submitted",
      output: {},
      stateChanges: { status: "reviewed" },
    },
    {
      nodeId: "create_issues",
      stepType: "use",
      resolvedInput: { report_id: "rpt_1" },
      outcome: "ok",
      output: { issues_created: 3 },
      stateChanges: {},
    },
  ],
  traceStart: 0,
  traceLimit: 50,
  traceTruncated: false,
};

describe("buildTraceFrames", () => {
  it("maps node ids correctly", () => {
    const result = buildTraceFrames(sampleTracePage);
    expect(result.frames.map((f) => f.nodeId)).toEqual([
      "start",
      "review",
      "create_issues",
    ]);
  });

  it("maps step types correctly", () => {
    const result = buildTraceFrames(sampleTracePage);
    expect(result.frames.map((f) => f.stepType)).toEqual(["use", "interrupt", "use"]);
  });

  it("maps outcomes correctly", () => {
    const result = buildTraceFrames(sampleTracePage);
    expect(result.frames.map((f) => f.outcome)).toEqual(["ok", "submitted", "ok"]);
  });

  it("produces concise input summaries", () => {
    const result = buildTraceFrames(sampleTracePage);
    expect(result.frames[1]!.inputSummary).toContain("report");
  });

  it("produces concise output summaries", () => {
    const result = buildTraceFrames(sampleTracePage);
    expect(result.frames[2]!.outputSummary).toContain("issues_created");
  });

  it("preserves original trace page immutability", () => {
    const original = structuredClone(sampleTracePage);
    buildTraceFrames(sampleTracePage);
    expect(sampleTracePage).toEqual(original);
  });

  it("handles empty trace page", () => {
    const result = buildTraceFrames({
      frames: [],
      traceStart: 0,
      traceLimit: 50,
      traceTruncated: false,
    });
    expect(result.frames).toEqual([]);
  });

  it("includes state change count", () => {
    const result = buildTraceFrames(sampleTracePage);
    expect(result.frames[1]!.stateChangeCount).toBe(1);
  });

  it("returns pagination info", () => {
    const result = buildTraceFrames(sampleTracePage);
    expect(result.traceStart).toBe(0);
    expect(result.traceLimit).toBe(50);
    expect(result.traceTruncated).toBe(false);
  });
});

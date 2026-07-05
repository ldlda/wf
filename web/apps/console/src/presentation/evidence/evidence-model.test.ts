import { describe, expect, it } from "vitest";
import type { EvidenceRecord } from "../../app/state.js";
import {
  formatEvidenceValue,
  projectEvidenceDetail,
  projectEvidenceReceipt,
} from "./evidence-model.js";

const record = (response: unknown): EvidenceRecord => ({
  id: "run-start",
  operation: "workflow.runs.start",
  label: "Start run",
  equivalentCli: "uv run wf run start demo.default",
  request: { deployment_id: "demo.default" },
  response,
  durationMs: 88,
});

describe("evidence projection", () => {
  it("uses the latest record and extracts a nested result status", () => {
    const model = projectEvidenceReceipt([
      record({ result: { status: "interrupted" } }),
      { ...record({ result: { status: "completed" } }), id: "trace", operation: "workflow.runs.trace" },
    ]);
    expect(model).toMatchObject({
      available: true,
      operation: "workflow.runs.trace",
      status: "completed",
      recordCount: 2,
    });
  });

  it("returns an unavailable receipt for no records", () => {
    expect(projectEvidenceReceipt([])).toEqual({
      available: false,
      operation: "Evidence unavailable",
      status: null,
      recordCount: 0,
    });
  });

  it("projects run and deployment identifiers without requiring status", () => {
    expect(projectEvidenceDetail({
      ...record({ result: { run_id: "run_demo" } }),
      request: { deployment_id: "demo.default" },
    })).toMatchObject({
      status: null,
      durationMs: 88,
      deploymentId: "demo.default",
      runId: "run_demo",
      equivalentCli: "uv run wf run start demo.default",
    });
  });

  it("returns bounded text and a note when raw evidence is not JSON serializable", () => {
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;
    const formatted = formatEvidenceValue(cyclic);
    expect(formatted.text).toBe("[object Object]");
    expect(formatted.note).toMatch(/could not format as json/i);
  });

  it("truncates oversized evidence before it reaches the inspector", () => {
    const formatted = formatEvidenceValue("x".repeat(120_000));
    expect(formatted.text.length).toBeLessThanOrEqual(100_003);
    expect(formatted.note).toMatch(/truncated/i);
  });
});

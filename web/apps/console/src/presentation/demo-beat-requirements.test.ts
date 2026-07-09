import { describe, expect, it } from "vitest";
import { requirementForDemoBeat } from "./demo-beat-requirements.js";

describe("requirementForDemoBeat", () => {
  it.each([
    ["workflow-demo", "operation", "run_start"],
    ["workflow-demo", "graph", "run_start"],
    ["workflow-demo", "interrupt", "interrupt"],
    ["interrupt-evidence", "approval", "interrupt"],
    ["interrupt-evidence", "resume", "run_resume"],
    ["interrupt-evidence", "output", "run_resume"],
    ["interrupt-evidence", "trace", "trace_read"],
  ] as const)("maps %s/%s to %s", (sceneId, beatId, stage) => {
    expect(requirementForDemoBeat(sceneId, beatId).requiredStage).toBe(stage);
  });

  it("returns no required stage for non-demo beats", () => {
    expect(requirementForDemoBeat("thesis", "title")).toEqual({
      requiredStage: null,
      reason: "No demo replay state needed.",
    });
  });
});

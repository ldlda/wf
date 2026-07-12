import { describe, expect, it } from "vitest";
import { requirementForDemoBeat } from "./demo-beat-requirements.js";

describe("requirementForDemoBeat", () => {
  it.each([
    ["prepared-lifecycle", "draft", "deployment_check"],
    ["prepared-lifecycle", "artifact", "deployment_check"],
    ["prepared-lifecycle", "deployment", "deployment_check"],
    ["prepared-lifecycle", "ready-run", "run_start"],
    ["run-from-deployment", "input", "run_start"],
    ["run-from-deployment", "operation", "run_start"],
    ["run-from-deployment", "graph", "run_start"],
    ["typed-human-boundary", "interrupt", "interrupt"],
    ["typed-human-boundary", "approval", "interrupt"],
    ["resume-output-evidence", "resume", "run_resume"],
    ["resume-output-evidence", "output", "run_resume"],
    ["resume-output-evidence", "trace", "trace_read"],
  ] as const)("maps %s/%s to %s", (sceneId, beatId, stage) => {
    expect(requirementForDemoBeat(sceneId, beatId).requiredStage).toBe(stage);
  });

  it("has no requirement for the removed Scene 11 cancel beat", () => {
    expect(requirementForDemoBeat("typed-human-boundary", "cancel")).toEqual({
      requiredStage: null,
      reason: "No demo replay state needed.",
    });
  });

  it("returns no required stage for non-demo beats", () => {
    expect(requirementForDemoBeat("thesis", "title")).toEqual({
      requiredStage: null,
      reason: "No demo replay state needed.",
    });
  });
});

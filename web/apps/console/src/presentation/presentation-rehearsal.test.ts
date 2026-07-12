import { describe, expect, it } from "vitest";
import { mainScenes } from "./storyboard.js";

const expectedBeats = {
  thesis: ["title", "substrate"],
  problem: ["direct-actions", "missing-contracts"],
  positioning: ["landscape", "lda-position"],
  "planner-runtime": ["planner", "runtime", "boundary"],
  lifecycle: ["draft", "artifact", "deployment", "run"],
  architecture: ["client", "api", "runtime", "node-use"],
  authoring: ["discover", "author", "diagnose", "repair"],
  "agent-handoff": ["request"],
  "prepared-lifecycle": ["discover", "draft", "validate", "artifact", "deployment"],
  "run-from-deployment": ["input", "operation", "graph"],
  "typed-human-boundary": ["interrupt", "approval"],
  "resume-output-evidence": ["resume", "output", "trace"],
  evaluation: ["cohort", "validity", "findings"],
  conclusion: ["limits", "future", "conclusion", "questions"],
} as const;

describe("presentation rehearsal storyboard", () => {
  it("keeps every scene count and canonical beat id aligned with the rehearsal", () => {
    expect(new Set(mainScenes.map((scene) => scene.id))).toEqual(new Set(Object.keys(expectedBeats)));

    for (const [sceneId, beatIds] of Object.entries(expectedBeats)) {
      const scene = mainScenes.find((candidate) => candidate.id === sceneId);
      expect(scene, `missing rehearsal scene ${sceneId}`).toBeDefined();
      if (!scene) continue;

      expect(scene.beats, `scene ${sceneId} has the wrong beat count`).toHaveLength(beatIds.length);
      for (const beatId of beatIds) {
        expect(
          scene.beats.map((beat) => beat.id),
          `scene ${sceneId} is missing beat ${beatId}`,
        ).toContain(beatId);
      }
    }
  });
});

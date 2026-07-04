import { describe, expect, it } from "vitest";
import {
  defaultMainLocation,
  discussionBranches,
  findBeat,
  findScene,
  mainScenes,
} from "./storyboard.js";

describe("defense storyboard catalog", () => {
  it("defines twelve ordered main scenes with unique scene and beat ids", () => {
    expect(mainScenes).toHaveLength(12);
    expect(mainScenes.map((scene) => scene.id)).toEqual([
      "thesis",
      "problem",
      "positioning",
      "planner-runtime",
      "lifecycle",
      "architecture",
      "authoring",
      "agent-handoff",
      "workflow-demo",
      "interrupt-evidence",
      "evaluation",
      "conclusion",
    ]);
    for (const scene of mainScenes) {
      expect(scene.beats.length).toBeGreaterThan(0);
      expect(new Set(scene.beats.map((beat) => beat.id)).size).toBe(scene.beats.length);
      expect(scene.claimClass.length).toBeGreaterThan(0);
      expect(scene.evidencePointer.length).toBeGreaterThan(0);
    }
  });

  it("uses act-level stage themes and independent chat composition", () => {
    expect(mainScenes.slice(0, 3).every((scene) => scene.stageTheme === "paper")).toBe(true);
    expect(mainScenes.slice(3, 10).every((scene) => scene.stageTheme === "night")).toBe(true);
    expect(mainScenes.slice(10).every((scene) => scene.stageTheme === "paper")).toBe(true);
    expect(findBeat("agent-handoff", "request")?.chatMode).toBe("full");
    expect(findBeat("workflow-demo", "graph")?.chatMode).toBe("rail");
    expect(findBeat("interrupt-evidence", "trace")?.chatMode).toBe("dock");
  });

  it("defines discussion branches across multiple scenes", () => {
    expect(discussionBranches.length).toBeGreaterThanOrEqual(5);
    const positioningBranches = discussionBranches.filter((b) => b.parentSceneId === "positioning");
    expect(positioningBranches.map((b) => b.id)).toEqual([
      "direct-orchestration",
      "generated-scripts",
      "hosted-automation",
      "durable-agent-graphs",
      "mcp-agent-scale",
    ]);
    for (const branch of discussionBranches) {
      expect(branch.title.length).toBeGreaterThan(0);
      expect(branch.summary.length).toBeGreaterThan(0);
      expect(branch.evidencePointer.length).toBeGreaterThan(0);
    }
  });

  it("exposes a valid default location", () => {
    expect(defaultMainLocation).toEqual({ kind: "main", sceneId: "thesis", beatId: "title" });
    expect(findScene(defaultMainLocation.sceneId)?.number).toBe(1);
  });
});

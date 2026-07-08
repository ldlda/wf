import { describe, expect, it } from "vitest";
import {
  defaultMainLocation,
  discussionBranches,
  findBeat,
  findScene,
  mainScenes,
  type DiscussionBranchDefinition,
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
      "not-just-scripts",
    ]);
    for (const branch of discussionBranches) {
      expect(branch.title.length).toBeGreaterThan(0);
      expect(branch.summary.length).toBeGreaterThan(0);
      expect(branch.evidencePointer.length).toBeGreaterThan(0);
    }
  });

  it("defines core defense Q&A branches for expected examiner questions", () => {
    expect(discussionBranches.map((branch) => branch.id)).toEqual(
      expect.arrayContaining([
        "where-is-ai-agent",
        "title-ai-agent-wording",
        "not-just-cli",
        "not-just-scripts",
        "evaluation-validity",
        "security-production-boundary",
        "demo-reliability",
        "prepared-replay-boundary",
        "why-schemas",
        "production-readiness",
      ]),
    );
  });

  it("keeps defense Q&A branches speaker-ready", () => {
    const branches: readonly DiscussionBranchDefinition[] = discussionBranches;
    const qnaBranches = branches.filter((branch) => branch.question);
    expect(qnaBranches.length).toBeGreaterThanOrEqual(10);
    for (const branch of qnaBranches) {
      expect(branch.question).toMatch(/\?$/);
      expect(branch.shortAnswer).toBeDefined();
      expect(branch.shortAnswer!.length).toBeGreaterThan(40);
      expect(branch.shortAnswer!.length).toBeLessThan(360);
      expect(branch.expandedAnswer).toBeDefined();
      expect(branch.expandedAnswer!.length).toBeGreaterThan(80);
      expect(branch.evidencePointer.length).toBeGreaterThan(0);
    }
  });

  it("exposes a valid default location", () => {
    expect(defaultMainLocation).toEqual({ kind: "main", sceneId: "thesis", beatId: "title", focusPath: [] });
    expect(findScene(defaultMainLocation.sceneId)?.number).toBe(1);
  });
});

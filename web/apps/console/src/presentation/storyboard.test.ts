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
  it("defines thirteen ordered main scenes with unique scene and beat ids", () => {
    expect(mainScenes).toHaveLength(13);
    expect(mainScenes.map((scene) => scene.id)).toEqual([
      "thesis",
      "problem",
      "positioning",
      "planner-runtime",
      "lifecycle",
      "architecture",
      "agent-handoff",
      "prepared-lifecycle",
      "run-from-deployment",
      "typed-human-boundary",
      "resume-output-evidence",
      "evaluation",
      "conclusion",
    ]);
    expect(findScene("architecture")?.beats.map((beat) => beat.id)).toEqual([
      "overview",
      "client",
      "api",
      "runtime",
    ]);
    expect(findScene("prepared-lifecycle")?.beats.map((beat) => beat.id)).toEqual([
      "discover",
      "draft",
      "diagnose",
      "repair",
      "artifact",
      "deployment",
    ]);
    expect(findScene("conclusion")?.number).toBe(13);
    expect(findScene("authoring")).toBeUndefined();
    for (const scene of mainScenes) {
      expect(scene.beats.length).toBeGreaterThan(0);
      expect(new Set(scene.beats.map((beat) => beat.id)).size).toBe(scene.beats.length);
      expect(scene.claimClass.length).toBeGreaterThan(0);
      expect(scene.evidencePointer.length).toBeGreaterThan(0);
    }
  });

  it("adds a hidden-chat questions beat after the conclusion beats", () => {
    expect(findBeat("conclusion", "questions")).toBeDefined();
    expect(findBeat("evaluation", "cohort")?.chatMode).toBe("hidden");
    expect(findBeat("conclusion", "conclusion")?.chatMode).toBe("hidden");
    expect(findBeat("conclusion", "questions")?.chatMode).toBe("hidden");
  });

  it("uses one editorial canvas theme and independent chat composition", () => {
    expect(findScene("agent-handoff")?.beats).toHaveLength(1);
    expect(findBeat("agent-handoff", "request")?.chatMode).toBe("hidden");
    expect(findBeat("resume-output-evidence", "trace")?.chatMode).toBe("hidden");
  });

  it("keeps chat out of the way during proof-heavy demo beats", () => {
    expect(findBeat("prepared-lifecycle", "discover")?.chatMode).toBe("hidden");
    expect(findBeat("prepared-lifecycle", "draft")?.chatMode).toBe("hidden");
    expect(findBeat("prepared-lifecycle", "diagnose")?.chatMode).toBe("hidden");
    expect(findBeat("prepared-lifecycle", "repair")?.chatMode).toBe("hidden");
    expect(findBeat("prepared-lifecycle", "artifact")?.chatMode).toBe("hidden");
    expect(findBeat("prepared-lifecycle", "deployment")?.chatMode).toBe("hidden");
    expect(findBeat("run-from-deployment", "input")?.chatMode).toBe("hidden");
    expect(findBeat("run-from-deployment", "graph")?.chatMode).toBe("hidden");
    expect(findBeat("typed-human-boundary", "approval")?.chatMode).toBe("hidden");
    expect(findBeat("resume-output-evidence", "resume")?.chatMode).toBe("hidden");
    expect(findBeat("resume-output-evidence", "output")?.chatMode).toBe("hidden");
    expect(findBeat("resume-output-evidence", "trace")?.chatMode).toBe("hidden");
  });

  it("splits the demo climax into lifecycle, run, interrupt, and evidence scenes", () => {
    expect(findScene("agent-handoff")?.number).toBe(7);
    expect(findScene("prepared-lifecycle")?.number).toBe(8);
    expect(findScene("run-from-deployment")?.number).toBe(9);
    expect(findScene("typed-human-boundary")?.number).toBe(10);
    expect(findScene("resume-output-evidence")?.number).toBe(11);
    expect(findScene("evaluation")?.number).toBe(12);
    expect(findScene("conclusion")?.number).toBe(13);
  });

  it("defines the lifecycle story beats before run evidence", () => {
    expect(findBeat("prepared-lifecycle", "discover")?.caption).toMatch(/sources|capabilities|schemas/i);
    expect(findBeat("prepared-lifecycle", "draft")?.caption).toMatch(/draft/i);
    expect(findBeat("prepared-lifecycle", "diagnose")?.caption).toBe(
      "Validation returns a structured diagnostic because analyze has no route for its ok outcome.",
    );
    expect(findBeat("prepared-lifecycle", "repair")?.caption).toBe(
      "One route edit sends analyze.ok to __end__; the follow-up validation is valid.",
    );
    expect(findBeat("prepared-lifecycle", "artifact")?.caption).toMatch(/compile|artifact/i);
    expect(findBeat("prepared-lifecycle", "deployment")?.caption).toMatch(/deploy|bindings/i);
  });

  it("keeps Scene 5 as vocabulary and moves applied lifecycle evidence to Scene 8", () => {
    expect(findBeat("lifecycle", "draft")?.caption).toMatch(/^Draft is mutable authoring state\.$/);
    expect(findBeat("lifecycle", "artifact")?.caption).toMatch(/^Artifact is an immutable workflow definition\.$/);
    expect(findBeat("lifecycle", "deployment")?.caption).toMatch(/^Deployment binds an artifact version/);
    expect(findBeat("lifecycle", "run")?.caption).toMatch(/^Run records one execution/);
    expect(findBeat("prepared-lifecycle", "diagnose")?.caption).toContain("no route for its ok outcome");
    expect(findBeat("prepared-lifecycle", "repair")?.caption).toContain("analyze.ok to __end__");
    expect(findBeat("prepared-lifecycle", "deployment")?.caption).toMatch(/ready|does not run|Scene 9/i);
    expect(findBeat("prepared-lifecycle", "deployment")?.caption).toMatch(/three-node|implementation extension/i);
  });

  it("makes the evaluation beat carry the audited counts and validity boundary", () => {
    expect(findBeat("evaluation", "cohort")?.caption).toMatch(/36|two challenges|two hosted models|three waves/i);
    expect(findBeat("evaluation", "validity")?.caption).toMatch(/27|8|1|audit/i);
    expect(findBeat("evaluation", "findings")?.caption).toMatch(/changing|longitudinal|benchmark/i);
  });

  it("defines focused run, interrupt, and evidence beats", () => {
    expect(findBeat("run-from-deployment", "input")).toBeDefined();
    expect(findBeat("run-from-deployment", "operation")).toBeDefined();
    expect(findBeat("run-from-deployment", "graph")).toBeDefined();
    expect(findBeat("typed-human-boundary", "interrupt")).toBeDefined();
    expect(findBeat("typed-human-boundary", "approval")).toBeDefined();
    expect(findBeat("resume-output-evidence", "resume")).toBeDefined();
    expect(findBeat("resume-output-evidence", "output")).toBeDefined();
    expect(findBeat("resume-output-evidence", "trace")).toBeDefined();
  });

  it("compresses Scene 11 into interrupt context and one operator decision beat", () => {
    expect(findScene("typed-human-boundary")?.beats.map((beat) => beat.id)).toEqual([
      "interrupt",
      "approval",
    ]);
    expect(findBeat("typed-human-boundary", "interrupt")?.caption).toMatch(/boundary|interrupt/i);
    expect(findBeat("typed-human-boundary", "approval")?.caption).toMatch(/decision|resume/i);
    expect(findBeat("typed-human-boundary", "cancel")).toBeUndefined();
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
    expect(
      discussionBranches
        .filter((branch) => branch.parentSceneId === "prepared-lifecycle")
        .map((branch) => branch.id),
    ).toEqual(expect.arrayContaining([
      "raw-plan-import",
      "validation-diagnostics",
      "why-schemas",
    ]));
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

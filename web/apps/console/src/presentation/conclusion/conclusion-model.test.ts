import { describe, expect, it } from "vitest";
import { contributionNodes, futureWorkBranches, isConclusionBeatId, nonClaims } from "./conclusion-model.js";

describe("conclusion model", () => {
  it("defines the stable contribution boundary", () => {
    expect(contributionNodes).toEqual([
      { id: "planner", label: "External planner" },
      { id: "substrate", label: "Typed workflow substrate" },
      { id: "runtime", label: "Deterministic runtime" },
      { id: "evidence", label: "Persisted, inspectable evidence" },
    ]);
  });

  it("keeps the closing claims bounded", () => {
    expect(nonClaims).toEqual(["Not a production sandbox", "Not a scheduler", "Not a broad agent benchmark"]);
    expect(isConclusionBeatId("limits")).toBe(true);
    expect(isConclusionBeatId("not-a-beat")).toBe(false);
  });

  it("names five distinct future-work layers with labelled examples", () => {
    expect(futureWorkBranches).toEqual([
      { id: "agent-interface", label: "Agent interface", example: "Chat or planner loop over wf operations", icon: "agent" },
      { id: "security", label: "Security and credentials", example: "Secrets, RBAC, sandboxing, policy", icon: "security" },
      { id: "scheduling", label: "Hosted operations", example: "Scheduling, daemon lifecycle, monitoring", icon: "schedule" },
      { id: "evaluation", label: "Controlled evaluation", example: "Frozen prompts, more trials, independent audit", icon: "evaluation" },
      { id: "runtime", label: "Runtime expansion", example: "Transactional stores, debugging, providers", icon: "runtime" },
    ]);
    expect(futureWorkBranches).toHaveLength(5);
    expect(new Set(futureWorkBranches.map((branch) => branch.id)).size).toBe(5);
    expect(new Set(futureWorkBranches.map((branch) => branch.icon)).size).toBe(5);
  });
});

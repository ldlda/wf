import { describe, expect, it } from "vitest";
import { discussionBranches } from "../storyboard.js";
import { discussionTopicByBranchId, projectDefenseDiscussionGroups } from "./defense-discussion-index.js";

describe("defense discussion index", () => {
  it("exhaustively projects every canonical discussion branch exactly once", () => {
    const groups = projectDefenseDiscussionGroups(discussionBranches);
    const indexedIds = groups.flatMap((group) => group.branches.map((branch) => branch.id));

    expect(indexedIds).toHaveLength(discussionBranches.length);
    expect(new Set(indexedIds)).toEqual(new Set(discussionBranches.map((branch) => branch.id)));
    expect(Object.keys(discussionTopicByBranchId).sort()).toEqual(
      discussionBranches.map((branch) => branch.id).sort(),
    );
  });

  it("derives indexed branch objects from the canonical definitions", () => {
    const groups = projectDefenseDiscussionGroups(discussionBranches);
    for (const branch of discussionBranches) {
      const indexed = groups.flatMap((group) => group.branches).find(({ id }) => id === branch.id);
      expect(indexed).toBe(branch);
    }
  });

  it("uses the scoped defense-topic labels from the closing design", () => {
    expect(projectDefenseDiscussionGroups(discussionBranches).map((group) => group.label)).toEqual([
      "Thesis contribution",
      "Positioning and related systems",
      "Runtime and lifecycle",
      "Authoring and validation",
      "Demo integrity",
      "Evaluation",
      "Production readiness and future work",
    ]);
  });
});

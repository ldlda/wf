import { describe, expect, it } from "vitest";
import { discussionBranches } from "../storyboard.js";
import { defenseDiscussionGroups, discussionTopicByBranchId } from "./defense-discussion-index.js";

describe("defense discussion index", () => {
  it("exhaustively projects every canonical discussion branch exactly once", () => {
    const indexedIds = defenseDiscussionGroups.flatMap((group) => group.branches.map((branch) => branch.id));

    expect(indexedIds).toHaveLength(discussionBranches.length);
    expect(new Set(indexedIds)).toEqual(new Set(discussionBranches.map((branch) => branch.id)));
    expect(Object.keys(discussionTopicByBranchId).sort()).toEqual(
      discussionBranches.map((branch) => branch.id).sort(),
    );
  });

  it("derives indexed branch objects from the canonical definitions", () => {
    for (const branch of discussionBranches) {
      const indexed = defenseDiscussionGroups.flatMap((group) => group.branches).find(({ id }) => id === branch.id);
      expect(indexed).toBe(branch);
    }
  });
});

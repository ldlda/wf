import { describe, expect, it } from "vitest";
import { audienceHrefForNote, formatPresenterTime, presenterNavigationFromHash } from "./presenter-navigation.js";

describe("presenter navigation", () => {
  it("resolves scene hashes with previous and next notes", () => {
    const navigation = presenterNavigationFromHash("#scene/problem/direct-actions");
    expect(navigation.note?.beatId).toBe("direct-actions");
    expect(navigation.previous?.beatId).toBe("substrate");
    expect(navigation.next?.beatId).toBe("missing-contracts");
    expect(navigation.cumulativeSeconds).toBeGreaterThan(0);
  });

  it("supports discussion hashes without inventing a speech note", () => {
    const navigation = presenterNavigationFromHash("#discuss/where-is-ai-agent");
    expect(navigation.location).toEqual({ kind: "discussion", branchId: "where-is-ai-agent" });
    expect(navigation.note).toBeNull();
  });

  it("fails closed to the first note", () => {
    expect(presenterNavigationFromHash("#scene/nope/nope").note?.beatId).toBe("title");
    expect(presenterNavigationFromHash("#%broken").note?.beatId).toBe("title");
  });

  it("builds audience links and readable timing", () => {
    const note = presenterNavigationFromHash("#scene/thesis/title").note;
    if (!note) throw new Error("missing note");
    expect(audienceHrefForNote(note)).toBe("/present#scene/thesis/title");
    expect(formatPresenterTime(83)).toBe("1:23");
  });
});

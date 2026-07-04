import { describe, expect, it } from "vitest";
import {
  hashForLocation,
  locationFromHash,
  nextMainLocation,
  previousMainLocation,
} from "./storyboard-navigation.js";
import { defaultMainLocation, type MainLocation } from "./storyboard.js";

describe("storyboard navigation", () => {
  it("round-trips main and discussion hashes", () => {
    const main: MainLocation = { kind: "main", sceneId: "lifecycle", beatId: "deployment" };
    expect(locationFromHash(hashForLocation(main))).toEqual(main);
    expect(locationFromHash("#discuss/hosted-automation")).toEqual({
      kind: "discussion",
      branchId: "hosted-automation",
    });
  });

  it("falls back for unknown scene, beat, and branch hashes", () => {
    expect(locationFromHash("#scene/missing/nope")).toEqual(defaultMainLocation);
    expect(locationFromHash("#scene/lifecycle/nope")).toEqual(defaultMainLocation);
    expect(locationFromHash("#discuss/nope")).toEqual(defaultMainLocation);
  });

  it("advances within a scene before advancing to the next scene", () => {
    expect(nextMainLocation({ kind: "main", sceneId: "thesis", beatId: "title" })).toEqual({
      kind: "main",
      sceneId: "thesis",
      beatId: "substrate",
    });
    expect(nextMainLocation({ kind: "main", sceneId: "thesis", beatId: "substrate" })).toEqual({
      kind: "main",
      sceneId: "problem",
      beatId: "direct-actions",
    });
  });

  it("rewinds across scene boundaries", () => {
    expect(previousMainLocation({ kind: "main", sceneId: "problem", beatId: "direct-actions" })).toEqual({
      kind: "main",
      sceneId: "thesis",
      beatId: "substrate",
    });
  });
});

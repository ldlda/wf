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
    const main: MainLocation = { kind: "main", sceneId: "lifecycle", beatId: "deployment", focusPath: [] };
    expect(locationFromHash(hashForLocation(main))).toEqual(main);
    expect(locationFromHash("#discuss/hosted-automation")).toEqual({
      kind: "discussion",
      branchId: "hosted-automation",
    });
    expect(locationFromHash("#discuss/where-is-ai-agent")).toEqual({
      kind: "discussion",
      branchId: "where-is-ai-agent",
    });
    expect(hashForLocation({ kind: "discussion", branchId: "where-is-ai-agent" }))
      .toBe("#discuss/where-is-ai-agent");
  });

  it("parses the Questions beat location", () => {
    expect(locationFromHash("#scene/conclusion/questions")).toEqual({
      kind: "main",
      sceneId: "conclusion",
      beatId: "questions",
      focusPath: [],
    });
  });

  it("falls back for unknown scene, beat, and branch hashes", () => {
    expect(locationFromHash("#scene/missing/nope")).toEqual(defaultMainLocation);
    expect(locationFromHash("#scene/lifecycle/nope")).toEqual(defaultMainLocation);
    expect(locationFromHash("#scene/agent-handoff/handoff")).toEqual(defaultMainLocation);
    expect(locationFromHash("#discuss/nope")).toEqual(defaultMainLocation);
  });

  it("falls back for malformed percent-encoded hashes", () => {
    expect(locationFromHash("#scene/%ZZ/%ZZ")).toEqual(defaultMainLocation);
    expect(locationFromHash("#discuss/%ZZ")).toEqual(defaultMainLocation);
  });

  it("round-trips a recursive Focus Path", () => {
    const location: MainLocation = {
      kind: "main",
      sceneId: "architecture",
      beatId: "runtime",
      focusPath: ["runtime-providers", "configured-providers"],
    };
    expect(hashForLocation(location)).toBe(
      "#scene/architecture/runtime/focus/runtime-providers/configured-providers",
    );
    expect(locationFromHash(hashForLocation(location))).toEqual(location);
  });

  it("decodes escaped focus segments and rejects malformed encoding", () => {
    expect(locationFromHash("#scene/architecture/runtime/focus/runtime%20providers"))
      .toMatchObject({ focusPath: ["runtime providers"] });
    expect(locationFromHash("#scene/architecture/runtime/focus/%ZZ"))
      .toEqual(defaultMainLocation);
  });

  it("advances within a scene before advancing to the next scene", () => {
    expect(nextMainLocation({ kind: "main", sceneId: "thesis", beatId: "title", focusPath: [] })).toEqual({
      kind: "main",
      sceneId: "thesis",
      beatId: "substrate",
      focusPath: [],
    });
    expect(nextMainLocation({ kind: "main", sceneId: "thesis", beatId: "substrate", focusPath: [] })).toEqual({
      kind: "main",
      sceneId: "problem",
      beatId: "direct-actions",
      focusPath: [],
    });
  });

  it("rewinds across scene boundaries", () => {
    expect(previousMainLocation({ kind: "main", sceneId: "problem", beatId: "direct-actions", focusPath: [] })).toEqual({
      kind: "main",
      sceneId: "thesis",
      beatId: "substrate",
      focusPath: [],
    });
  });
});

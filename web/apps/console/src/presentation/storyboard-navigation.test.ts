import { describe, expect, it } from "vitest";
import rehearsalRoutes from "../../../../../scripts/presentation-rehearsal-routes.json";
import {
  hashForLocation,
  locationFromHash,
  nextMainLocation,
  previousMainLocation,
} from "./storyboard-navigation.js";
import { defaultMainLocation, mainScenes, type MainLocation } from "./storyboard.js";

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

  it("round-trips every current storyboard beat", () => {
    const storyboardRoutes = mainScenes.flatMap((scene) =>
      scene.beats.map((beat) => `${scene.id}/${beat.id}`),
    );
    const manifestRoutes = rehearsalRoutes.map((route) => `${route.sceneId}/${route.beatId}`);

    expect(new Set(manifestRoutes).size).toBe(manifestRoutes.length);
    expect(manifestRoutes).toHaveLength(storyboardRoutes.length);

    for (const scene of mainScenes) {
      for (const beat of scene.beats) {
        const matchingRoutes = rehearsalRoutes.filter(
          (route) => route.sceneId === scene.id && route.beatId === beat.id,
        );
        expect(matchingRoutes, `missing rehearsal route for scene ${scene.id}`).toHaveLength(1);
        const route = matchingRoutes[0];
        if (!route) continue;
        expect(route).toMatchObject({
          sceneId: scene.id,
          beatId: beat.id,
          route: `${scene.id}/${beat.id}`,
        });
        expect(locationFromHash(hashForLocation({
          kind: "main",
          sceneId: scene.id,
          beatId: beat.id,
          focusPath: [],
        }))).toEqual({
          kind: "main",
          sceneId: scene.id,
          beatId: beat.id,
          focusPath: [],
        });
      }
    }

    for (const route of rehearsalRoutes) {
      expect(Object.keys(route).sort()).toEqual(["beatId", "fileStem", "route", "sceneId"]);
      expect(storyboardRoutes).toContain(`${route.sceneId}/${route.beatId}`);
      expect(locationFromHash(hashForLocation({
        kind: "main",
        sceneId: route.sceneId as MainLocation["sceneId"],
        beatId: route.beatId,
        focusPath: [],
      }))).toMatchObject({
        kind: "main",
        sceneId: route.sceneId,
        beatId: route.beatId,
        focusPath: [],
      });
    }
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

  it("uses each architecture beat's authored focus for a plain direct hash", () => {
    expect(locationFromHash("#scene/architecture/api")).toMatchObject({
      focusPath: ["application-lifecycle"],
    });
    expect(locationFromHash("#scene/architecture/runtime")).toMatchObject({
      focusPath: ["runtime-providers"],
    });
  });

  it("round-trips NodeUse as an optional architecture deep dive", () => {
    const nodeUseDeepDive = {
      kind: "main" as const,
      sceneId: "architecture" as const,
      beatId: "overview",
      focusPath: ["node-use"],
    };

    expect(hashForLocation(nodeUseDeepDive)).toBe(
      "#scene/architecture/overview/focus/node-use",
    );
    expect(locationFromHash(hashForLocation(nodeUseDeepDive))).toEqual(nodeUseDeepDive);
  });

  it("round-trips an explicit root view for a beat with an authored nested focus", () => {
    const rootView: MainLocation = {
      kind: "main",
      sceneId: "architecture",
      beatId: "runtime",
      focusPath: [],
    };

    expect(hashForLocation(rootView)).toBe("#scene/architecture/runtime/focus/~");
    expect(locationFromHash(hashForLocation(rootView))).toEqual(rootView);
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

  it("advances Scene 11 directly from interrupt to approval, then Scene 12", () => {
    const interrupt = { kind: "main", sceneId: "typed-human-boundary", beatId: "interrupt", focusPath: [] } as const;
    const approval = { kind: "main", sceneId: "typed-human-boundary", beatId: "approval", focusPath: [] } as const;

    expect(nextMainLocation(interrupt)).toEqual(approval);
    expect(nextMainLocation(approval)).toMatchObject({
      kind: "main",
      sceneId: "resume-output-evidence",
      beatId: "resume",
    });
  });

  it("fails closed for the removed Scene 11 cancel hash", () => {
    expect(locationFromHash("#scene/typed-human-boundary/cancel")).toEqual(defaultMainLocation);
  });
});

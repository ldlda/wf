import { describe, expect, it } from "vitest";
import {
  compositionForState,
  initialPresentationState,
  presentationReducer,
} from "./presentation-state.js";
import type { MainLocation } from "./storyboard.js";

describe("presentationReducer", () => {
  it("advances within a scene before advancing to the next scene", () => {
    const advanced = presentationReducer(initialPresentationState, { type: "next" });
    expect(advanced.location).toEqual({ kind: "main", sceneId: "thesis", beatId: "substrate", focusPath: [] });

    const advancedAgain = presentationReducer(advanced, { type: "next" });
    expect(advancedAgain.location).toEqual({ kind: "main", sceneId: "problem", beatId: "direct-actions", focusPath: [] });
  });

  it("rewinds across scene boundaries", () => {
    const state: MainLocation = { kind: "main", sceneId: "problem", beatId: "direct-actions", focusPath: [] };
    const rewound = presentationReducer(
      { ...initialPresentationState, location: state },
      { type: "previous" },
    );
    expect(rewound.location).toEqual({ kind: "main", sceneId: "thesis", beatId: "substrate", focusPath: [] });
  });

  it("jumps to a specific scene and beat", () => {
    const jumped = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "workflow-demo", beatId: "graph", focusPath: [] },
    });
    expect(jumped.location).toEqual({ kind: "main", sceneId: "workflow-demo", beatId: "graph", focusPath: [] });
  });

  it("parses a scene hash", () => {
    const state = presentationReducer(initialPresentationState, {
      type: "jump_hash",
      hash: "#scene/lifecycle/deployment",
    });
    expect(state.location).toEqual({ kind: "main", sceneId: "lifecycle", beatId: "deployment", focusPath: [] });
  });

  it("falls back to default for invalid hash", () => {
    const state = presentationReducer(initialPresentationState, {
      type: "jump_hash",
      hash: "#scene/nope/nope",
    });
    expect(state.location).toEqual({ kind: "main", sceneId: "thesis", beatId: "title", focusPath: [] });
  });

  it("opens a discussion branch and returns to the originating beat", () => {
    const positioned = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "positioning", beatId: "lda-position", focusPath: [] },
    });
    const opened = presentationReducer(positioned, {
      type: "open_discussion",
      branchId: "hosted-automation",
    });
    const closed = presentationReducer(opened, { type: "close_discussion" });

    expect(opened.location).toEqual({ kind: "discussion", branchId: "hosted-automation" });
    expect(closed.location).toEqual(positioned.location);
  });

  it("opens node detail without changing the current location", () => {
    const state = presentationReducer(initialPresentationState, {
      type: "select_node",
      nodeId: "review_issues",
    });
    expect(state.location).toEqual(initialPresentationState.location);
    expect(state.selectedNodeId).toBe("review_issues");
  });

  it("closes overlays in priority order: node, evidence, discussion", () => {
    const withNode = presentationReducer(initialPresentationState, {
      type: "select_node",
      nodeId: "review_issues",
    });
    const withEvidence = presentationReducer(withNode, {
      type: "set_evidence_mode",
      mode: "open",
    });
    const opened = presentationReducer(withEvidence, {
      type: "open_discussion",
      branchId: "hosted-automation",
    });

    const closed1 = presentationReducer(opened, { type: "close_overlay" });
    expect(closed1.selectedNodeId).toBeNull();
    expect(closed1.evidenceModeOverride).toBe("open");
    expect(closed1.location.kind).toBe("discussion");

    const closed2 = presentationReducer(closed1, { type: "close_overlay" });
    expect(closed2.evidenceModeOverride).toBe("hidden");

    const closed3 = presentationReducer(closed2, { type: "close_overlay" });
    expect(closed3.location.kind).toBe("main");
  });

  it("does nothing on next while a discussion branch is open", () => {
    const positioned = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "thesis", beatId: "title", focusPath: [] },
    });
    const opened = presentationReducer(positioned, {
      type: "open_discussion",
      branchId: "direct-orchestration",
    });
    const nexted = presentationReducer(opened, { type: "next" });
    expect(nexted.location).toEqual(opened.location);
  });

  it("derives act and chat composition from the current beat", () => {
    const state = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "workflow-demo", beatId: "graph", focusPath: [] },
    });
    expect(compositionForState(state)).toMatchObject({
      stageTheme: "night",
      chatTheme: "light",
      chatMode: "rail",
    });
  });

  it("closes overlays before rewinding content", () => {
    const opened = presentationReducer(initialPresentationState, {
      type: "set_evidence_mode",
      mode: "open",
    });
    const closed = presentationReducer(opened, { type: "close_overlay" });
    expect(closed.evidenceModeOverride).toBe("hidden");
    expect(closed.location).toEqual(initialPresentationState.location);
  });

  it("does not reopen evidence on repeated Escape after force-close", () => {
    const stateAtTrace = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "interrupt-evidence", beatId: "trace", focusPath: [] },
    });
    expect(stateAtTrace.evidenceModeOverride).toBeNull();

    const closed = presentationReducer(stateAtTrace, { type: "close_overlay" });
    expect(closed.evidenceModeOverride).toBe("hidden");

    const secondEscape = presentationReducer(closed, { type: "close_overlay" });
    expect(secondEscape.evidenceModeOverride).toBe("hidden");
    expect(secondEscape.location.kind).toBe("main");
  });

  it("sets focus without changing scene or beat", () => {
    const focused = presentationReducer(initialPresentationState, {
      type: "set_focus_path",
      path: ["runtime-providers"],
    });
    expect(focused.location).toEqual({
      ...initialPresentationState.location,
      focusPath: ["runtime-providers"],
    });
  });

  it("next applies the destination beat canonical Focus Path", () => {
    const manuallyFocused = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "thesis", beatId: "title", focusPath: ["manual-explore"] },
    });
    const next = presentationReducer(manuallyFocused, { type: "next" });
    expect(next.location).toEqual({
      kind: "main",
      sceneId: "thesis",
      beatId: "substrate",
      focusPath: [],
    });
  });

  it("discussion return restores the exact Focus Path", () => {
    const deepRuntimeState = {
      ...initialPresentationState,
      location: { kind: "main" as const, sceneId: "architecture" as const, beatId: "runtime", focusPath: ["runtime-providers"] },
    };
    const opened = presentationReducer(deepRuntimeState, {
      type: "open_discussion",
      branchId: "provider-security",
    });
    expect(presentationReducer(opened, { type: "close_discussion" }).location)
      .toEqual(deepRuntimeState.location);
  });
});

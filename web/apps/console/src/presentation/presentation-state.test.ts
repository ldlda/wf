import { describe, expect, it } from "vitest";
import {
  compositionForState,
  createInitialPresentationState,
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
      location: { kind: "main", sceneId: "run-from-deployment", beatId: "graph", focusPath: [] },
    });
    expect(jumped.location).toEqual({ kind: "main", sceneId: "run-from-deployment", beatId: "graph", focusPath: [] });
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

  it("clears evidence overrides when deep-linking into a discussion branch", () => {
    const state = presentationReducer(
      {
        ...initialPresentationState,
        evidencePresentationOverride: "inspector",
      },
      {
        type: "jump_hash",
        hash: "#discuss/hosted-automation",
      },
    );

    expect(state.location).toEqual({ kind: "discussion", branchId: "hosted-automation" });
    expect(state.evidencePresentationOverride).toBeNull();
    expect(state.discussionReturn).toEqual({ kind: "main", sceneId: "positioning", beatId: "landscape", focusPath: [] });
  });

  it("creates fresh startedAt values per reducer session", () => {
    expect(createInitialPresentationState(100).startedAt).toBe(100);
    expect(createInitialPresentationState(250).startedAt).toBe(250);
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

  it("clears node detail through nullable selection", () => {
    const withNode = presentationReducer(initialPresentationState, {
      type: "select_node",
      nodeId: "review_issues",
    });
    const cleared = presentationReducer(withNode, {
      type: "select_node",
      nodeId: null,
    });
    expect(cleared.selectedNodeId).toBeNull();
  });

  it("closes overlays in priority order: inspector, node, discussion", () => {
    const withNode = presentationReducer(initialPresentationState, {
      type: "select_node",
      nodeId: "review_issues",
    });
    const withInspector = presentationReducer(withNode, {
      type: "set_evidence_presentation",
      presentation: "inspector",
    });
    const opened = presentationReducer(withInspector, {
      type: "open_discussion",
      branchId: "hosted-automation",
    });

    expect(opened.evidencePresentationOverride).toBeNull();
    expect(opened.selectedNodeId).toBe("review_issues");
    expect(opened.location.kind).toBe("discussion");

    const closed1 = presentationReducer(opened, { type: "close_overlay" });
    expect(closed1.selectedNodeId).toBeNull();
    expect(closed1.location.kind).toBe("discussion");

    const closed2 = presentationReducer(closed1, { type: "close_overlay" });
    expect(closed2.location.kind).toBe("main");
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

  it("derives chatMode from the current beat", () => {
    const state = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "run-from-deployment", beatId: "graph", focusPath: [] },
    });
    expect(compositionForState(state)).toMatchObject({
      chatMode: "hidden",
    });
  });

  it("closes overlays before rewinding content", () => {
    const opened = presentationReducer(initialPresentationState, {
      type: "set_evidence_presentation",
      presentation: "inspector",
    });
    const closed = presentationReducer(opened, { type: "close_overlay" });
    expect(closed.evidencePresentationOverride).toBeNull();
    expect(closed.location).toEqual(initialPresentationState.location);
  });

  it("does not reopen evidence on repeated Escape after force-close", () => {
    const stateAtTrace = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "resume-output-evidence", beatId: "trace", focusPath: [] },
    });
    expect(stateAtTrace.evidencePresentationOverride).toBeNull();

    const closed = presentationReducer(stateAtTrace, { type: "close_overlay" });
    expect(closed.evidencePresentationOverride).toBeNull();
    expect(closed.location.kind).toBe("main");

    const secondEscape = presentationReducer(closed, { type: "close_overlay" });
    expect(secondEscape.evidencePresentationOverride).toBeNull();
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

  it("preserves the questions beat as the discussion return location", () => {
    const atQuestions = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "conclusion", beatId: "questions", focusPath: [] },
    });
    const opened = presentationReducer(atQuestions, {
      type: "open_discussion",
      branchId: "where-is-ai-agent",
    });

    expect(opened.discussionReturn).toEqual(atQuestions.location);
    expect(presentationReducer(opened, { type: "close_discussion" }).location).toEqual(atQuestions.location);
  });

  it("derives a receipt from beat metadata without opening an inspector", () => {
    const state = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "architecture", beatId: "node-use", focusPath: ["node-use"] },
    });
    expect(compositionForState(state).evidencePresentation).toBe("receipt");
    expect(state.evidencePresentationOverride).toBeNull();
  });

  it("closes an explicit inspector before the node spotlight", () => {
    const withNode = presentationReducer(initialPresentationState, {
      type: "select_node",
      nodeId: "review_issues",
    });
    const withInspector = presentationReducer(withNode, {
      type: "set_evidence_presentation",
      presentation: "inspector",
    });
    const firstEscape = presentationReducer(withInspector, { type: "close_overlay" });
    expect(firstEscape.evidencePresentationOverride).toBeNull();
    expect(firstEscape.selectedNodeId).toBe("review_issues");
    const secondEscape = presentationReducer(firstEscape, { type: "close_overlay" });
    expect(secondEscape.selectedNodeId).toBeNull();
  });

  it("returns to the beat receipt after closing an explicit inspector", () => {
    const atReceiptBeat = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "resume-output-evidence", beatId: "trace", focusPath: [] },
    });
    expect(compositionForState(atReceiptBeat).evidencePresentation).toBe("receipt");
    const opened = presentationReducer(atReceiptBeat, {
      type: "set_evidence_presentation",
      presentation: "inspector",
    });
    expect(compositionForState(opened).evidencePresentation).toBe("inspector");

    const closed = presentationReducer(opened, { type: "close_overlay" });
    expect(closed.evidencePresentationOverride).toBeNull();
    expect(compositionForState(closed).evidencePresentation).toBe("receipt");
  });

  it("closes the inspector and recomputes receipt state when the beat changes", () => {
    const atReceiptBeat = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "architecture", beatId: "node-use", focusPath: ["node-use"] },
    });
    const opened = presentationReducer(atReceiptBeat, {
      type: "set_evidence_presentation",
      presentation: "inspector",
    });
    const advanced = presentationReducer(opened, { type: "next" });
    expect(advanced.evidencePresentationOverride).toBeNull();
    expect(compositionForState(advanced).evidencePresentation).not.toBe("inspector");
  });

  it("does not treat a receipt as an Escape-closeable overlay", () => {
    const receipt = presentationReducer(initialPresentationState, {
      type: "jump",
      location: { kind: "main", sceneId: "authoring", beatId: "diagnose", focusPath: [] },
    });
    expect(presentationReducer(receipt, { type: "close_overlay" })).toEqual(receipt);
  });
});

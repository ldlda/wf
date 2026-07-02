import { describe, expect, it } from "vitest";
import {
  initialPresentationState,
  presentationReducer,
} from "./presentation-state.js";

describe("presentationReducer", () => {
  it("advances and rewinds scripted beats without changing playback mode", () => {
    const advanced = presentationReducer(initialPresentationState, { type: "next" });
    const rewound = presentationReducer(advanced, { type: "previous" });

    expect(advanced.beat).toBe("chat-request");
    expect(advanced.playbackMode).toBe("replay");
    expect(rewound.beat).toBe("intro");
  });

  it("opens node detail without changing the current beat", () => {
    const state = presentationReducer(initialPresentationState, {
      type: "select_node",
      nodeId: "review_issues",
    });

    expect(state.beat).toBe("intro");
    expect(state.selectedNodeId).toBe("review_issues");
  });

  it("closes overlays before rewinding content", () => {
    const opened = presentationReducer(initialPresentationState, {
      type: "set_evidence_mode",
      mode: "open",
    });
    const closed = presentationReducer(opened, { type: "close_overlay" });

    expect(closed.evidenceMode).toBe("hidden");
    expect(closed.beat).toBe("intro");
  });

  it("closes node spotlight before evidence drawer", () => {
    const withNode = presentationReducer(initialPresentationState, {
      type: "select_node",
      nodeId: "review_issues",
    });
    const withEvidence = presentationReducer(withNode, {
      type: "set_evidence_mode",
      mode: "open",
    });

    expect(withEvidence.selectedNodeId).toBe("review_issues");
    expect(withEvidence.evidenceMode).toBe("open");

    const afterEscape = presentationReducer(withEvidence, { type: "close_overlay" });
    expect(afterEscape.selectedNodeId).toBeNull();
    expect(afterEscape.evidenceMode).toBe("open");
  });
});

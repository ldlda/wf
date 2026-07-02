import { beatFromHash, presentationBeats, type BeatId } from "./beats.js";

export type PresentationState = {
  readonly beat: BeatId;
  readonly selectedNodeId: string | null;
  readonly chatMode: "full" | "rail" | "hidden";
  readonly evidenceMode: "hidden" | "peek" | "open";
  readonly playbackMode: "replay" | "live";
};

export type PresentationAction =
  | { readonly type: "next" }
  | { readonly type: "previous" }
  | { readonly type: "jump"; readonly beat: BeatId }
  | { readonly type: "jump_hash"; readonly hash: string }
  | { readonly type: "select_node"; readonly nodeId: string }
  | { readonly type: "clear_node" }
  | { readonly type: "set_evidence_mode"; readonly mode: PresentationState["evidenceMode"] }
  | { readonly type: "close_overlay" }
  | { readonly type: "set_playback_mode"; readonly mode: PresentationState["playbackMode"] };

export const initialPresentationState: PresentationState = {
  beat: "intro",
  selectedNodeId: null,
  chatMode: "full",
  evidenceMode: "hidden",
  playbackMode: "replay",
};

const beatIndex = (beat: BeatId): number =>
  presentationBeats.findIndex((candidate) => candidate.id === beat);

const withDerivedModes = (state: PresentationState, beat: BeatId): PresentationState => ({
  ...state,
  beat,
  chatMode: beat === "intro" || beat === "chat-request" ? "full" : "rail",
  evidenceMode: beat === "trace-evidence" ? "peek" : state.evidenceMode,
});

export const presentationReducer = (
  state: PresentationState,
  action: PresentationAction,
): PresentationState => {
  switch (action.type) {
    case "next": {
      const next = Math.min(beatIndex(state.beat) + 1, presentationBeats.length - 1);
      return withDerivedModes(state, presentationBeats[next]?.id ?? state.beat);
    }
    case "previous": {
      const previous = Math.max(beatIndex(state.beat) - 1, 0);
      return withDerivedModes(state, presentationBeats[previous]?.id ?? state.beat);
    }
    case "jump":
      return withDerivedModes(state, action.beat);
    case "jump_hash":
      return withDerivedModes(state, beatFromHash(action.hash));
    case "select_node":
      return { ...state, selectedNodeId: action.nodeId };
    case "clear_node":
      return { ...state, selectedNodeId: null };
    case "set_evidence_mode":
      return { ...state, evidenceMode: action.mode };
    case "close_overlay":
      if (state.selectedNodeId !== null) return { ...state, selectedNodeId: null };
      if (state.evidenceMode !== "hidden") return { ...state, evidenceMode: "hidden" };
      return state;
    case "set_playback_mode":
      return { ...state, playbackMode: action.mode };
  }
};

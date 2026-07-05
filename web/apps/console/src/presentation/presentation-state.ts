import {
  defaultMainLocation,
  findDiscussionBranch,
  findScene,
  type ChatMode,
  type DiscussionBranchId,
  type EvidenceMode,
  type MainLocation,
  type PresentationLocation,
} from "./storyboard.js";
import {
  hashForLocation,
  locationFromHash,
  nextMainLocation,
  previousMainLocation,
} from "./storyboard-navigation.js";

export type PresentationState = {
  readonly location: PresentationLocation;
  readonly discussionReturn: MainLocation | null;
  readonly selectedNodeId: string | null;
  readonly evidenceModeOverride: EvidenceMode | null;
  readonly playbackMode: "replay" | "live";
  readonly motionDisabled: boolean;
  readonly startedAt: number;
};

export type PresentationAction =
  | { readonly type: "next" }
  | { readonly type: "previous" }
  | { readonly type: "jump"; readonly location: PresentationLocation }
  | { readonly type: "jump_hash"; readonly hash: string }
  | { readonly type: "open_discussion"; readonly branchId: string }
  | { readonly type: "close_discussion" }
  | { readonly type: "select_node"; readonly nodeId: string }
  | { readonly type: "clear_node" }
  | { readonly type: "set_evidence_mode"; readonly mode: EvidenceMode }
  | { readonly type: "close_overlay" }
  | { readonly type: "set_playback_mode"; readonly mode: PresentationState["playbackMode"] }
  | { readonly type: "set_focus_path"; readonly path: readonly string[] }
  | { readonly type: "toggle_motion" };

export const initialPresentationState: PresentationState = {
  location: defaultMainLocation,
  discussionReturn: null,
  selectedNodeId: null,
  evidenceModeOverride: null,
  playbackMode: "replay",
  motionDisabled: false,
  startedAt: Date.now(),
};

const compositionForLocation = (
  location: PresentationLocation,
  evidenceOverride: EvidenceMode | null,
): {
  readonly chatMode: ChatMode;
  readonly evidenceMode: EvidenceMode;
} => {
  if (location.kind === "discussion") {
    return {
      chatMode: "hidden",
      evidenceMode: evidenceOverride ?? "hidden",
    };
  }
  const scene = findScene(location.sceneId);
  const beat = scene?.beats.find((b) => b.id === location.beatId);
  return {
    chatMode: beat?.chatMode ?? "hidden",
    evidenceMode: evidenceOverride ?? beat?.evidenceMode ?? "hidden",
  };
};

export const compositionForState = (state: PresentationState) =>
  compositionForLocation(
    state.location,
    state.evidenceModeOverride,
  );

const isValidMainLocation = (location: PresentationLocation): location is MainLocation =>
  location.kind === "main";

const firstBeatOfScene = (sceneId: string): MainLocation | null => {
  const scene = findScene(sceneId);
  if (!scene || scene.beats.length === 0) return null;
  const beat = scene.beats[0]!;
  return { kind: "main", sceneId: scene.id as MainLocation["sceneId"], beatId: beat.id, focusPath: beat.figure?.focusPath ?? [] };
};

const clampMainLocation = (location: MainLocation): MainLocation => {
  const found = findScene(location.sceneId)?.beats.some((b) => b.id === location.beatId);
  if (found) return location;
  return defaultMainLocation;
};

export const presentationReducer = (
  state: PresentationState,
  action: PresentationAction,
): PresentationState => {
  switch (action.type) {
    case "next": {
      if (!isValidMainLocation(state.location)) return state;
      const next = nextMainLocation(state.location);
      return { ...state, location: next };
    }
    case "previous": {
      if (!isValidMainLocation(state.location)) return state;
      const prev = previousMainLocation(state.location);
      return { ...state, location: prev };
    }
    case "jump": {
      if (state.location.kind === "discussion") return state;
      return { ...state, location: action.location };
    }
    case "jump_hash": {
      const parsed = locationFromHash(action.hash);
      if (parsed.kind === "main") {
        return { ...state, location: clampMainLocation(parsed), discussionReturn: null };
      }
      const branch = findDiscussionBranch(parsed.branchId);
      const returnLoc = branch
        ? firstBeatOfScene(branch.parentSceneId) ?? defaultMainLocation
        : defaultMainLocation;
      return { ...state, location: parsed, discussionReturn: returnLoc };
    }
    case "open_discussion": {
      const branch = findDiscussionBranch(action.branchId);
      if (!branch) return state;
      const returnLocation = isValidMainLocation(state.location)
        ? state.location
        : firstBeatOfScene(branch.parentSceneId) ?? defaultMainLocation;
      return {
        ...state,
        location: { kind: "discussion", branchId: action.branchId as DiscussionBranchId },
        discussionReturn: returnLocation,
      };
    }
    case "close_discussion": {
      if (state.location.kind !== "discussion") return state;
      return {
        ...state,
        location: state.discussionReturn ?? defaultMainLocation,
        discussionReturn: null,
      };
    }
    case "select_node":
      return { ...state, selectedNodeId: action.nodeId };
    case "clear_node":
      return { ...state, selectedNodeId: null };
    case "set_evidence_mode":
      return { ...state, evidenceModeOverride: action.mode };
    case "close_overlay": {
      if (state.selectedNodeId !== null) return { ...state, selectedNodeId: null };
      const isEvidenceVisible = (() => {
        if (state.evidenceModeOverride !== null) return state.evidenceModeOverride !== "hidden";
        if (state.location.kind === "discussion") return false;
        const scene = findScene(state.location.sceneId);
        const beat = scene?.beats.find((b) => b.id === (state.location as MainLocation).beatId);
        return beat?.evidenceMode === "open" || beat?.evidenceMode === "peek";
      })();
      if (isEvidenceVisible) return { ...state, evidenceModeOverride: "hidden" };
      if (state.location.kind === "discussion") {
        return {
          ...state,
          location: state.discussionReturn ?? defaultMainLocation,
          discussionReturn: null,
        };
      }
      return state;
    }
    case "set_playback_mode":
      return { ...state, playbackMode: action.mode };
    case "set_focus_path":
      if (state.location.kind !== "main") return state;
      return {
        ...state,
        location: { ...state.location, focusPath: action.path },
      };
    case "toggle_motion":
      return { ...state, motionDisabled: !state.motionDisabled };
  }
};

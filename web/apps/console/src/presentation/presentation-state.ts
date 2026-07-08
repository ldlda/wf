import {
  defaultMainLocation,
  findDiscussionBranch,
  findScene,
  type BeatEvidencePresentation,
  type ChatMode,
  type ChatTheme,
  type DiscussionBranchId,
  type EvidencePresentation,
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
  readonly evidencePresentationOverride: EvidencePresentation | null;
  readonly playbackMode: "replay" | "live";
  readonly motionDisabled: boolean;
  readonly startedAt: number;
};

export type PresentationAction =
  | { readonly type: "next" }
  | { readonly type: "previous" }
  | { readonly type: "jump"; readonly location: MainLocation }
  | { readonly type: "jump_hash"; readonly hash: string }
  | { readonly type: "open_discussion"; readonly branchId: string }
  | { readonly type: "close_discussion" }
  | { readonly type: "select_node"; readonly nodeId: string | null }
  | { readonly type: "clear_node" }
  | { readonly type: "set_evidence_presentation"; readonly presentation: EvidencePresentation }
  | { readonly type: "close_overlay" }
  | { readonly type: "set_playback_mode"; readonly mode: PresentationState["playbackMode"] }
  | { readonly type: "set_focus_path"; readonly path: readonly string[] }
  | { readonly type: "toggle_motion" };

export const createInitialPresentationState = (startedAt = Date.now()): PresentationState => ({
  location: defaultMainLocation,
  discussionReturn: null,
  selectedNodeId: null,
  evidencePresentationOverride: null,
  playbackMode: "replay",
  motionDisabled: false,
  startedAt,
});

export const initialPresentationState: PresentationState = createInitialPresentationState();

const compositionForLocation = (
  location: PresentationLocation,
  evidenceOverride: EvidencePresentation | null,
): {
  readonly chatMode: ChatMode;
  readonly chatTheme: ChatTheme;
  readonly evidencePresentation: EvidencePresentation;
} => {
  if (location.kind === "discussion") {
    return {
      chatMode: "hidden",
      chatTheme: "dark",
      evidencePresentation: evidenceOverride ?? "hidden",
    };
  }
  const scene = findScene(location.sceneId);
  const beat = scene?.beats.find((b) => b.id === location.beatId);
  return {
    chatMode: beat?.chatMode ?? "hidden",
    chatTheme: beat?.chatTheme ?? "dark",
    evidencePresentation: evidenceOverride ?? beat?.evidencePresentation ?? "hidden",
  };
};

export const compositionForState = (state: PresentationState) =>
  compositionForLocation(
    state.location,
    state.evidencePresentationOverride,
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

const moveToLocation = (
  state: PresentationState,
  location: PresentationLocation,
): PresentationState => ({
  ...state,
  location,
});

export const presentationReducer = (
  state: PresentationState,
  action: PresentationAction,
): PresentationState => {
  switch (action.type) {
    case "next": {
      if (!isValidMainLocation(state.location)) return state;
      const next = nextMainLocation(state.location);
      return { ...moveToLocation(state, next), evidencePresentationOverride: null };
    }
    case "previous": {
      if (!isValidMainLocation(state.location)) return state;
      const prev = previousMainLocation(state.location);
      return { ...moveToLocation(state, prev), evidencePresentationOverride: null };
    }
    case "jump": {
      if (state.location.kind === "discussion") return state;
      return { ...moveToLocation(state, action.location), evidencePresentationOverride: null };
    }
    case "jump_hash": {
      const parsed = locationFromHash(action.hash);
      if (parsed.kind === "main") {
        return { ...moveToLocation(state, clampMainLocation(parsed)), discussionReturn: null, evidencePresentationOverride: null };
      }
      const branch = findDiscussionBranch(parsed.branchId);
      const returnLoc = branch
        ? firstBeatOfScene(branch.parentSceneId) ?? defaultMainLocation
        : defaultMainLocation;
      return {
        ...moveToLocation(state, parsed),
        discussionReturn: returnLoc,
        evidencePresentationOverride: null,
      };
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
        evidencePresentationOverride: null,
      };
    }
    case "close_discussion": {
      if (state.location.kind !== "discussion") return state;
      return {
        ...moveToLocation(state, state.discussionReturn ?? defaultMainLocation),
        discussionReturn: null,
      };
    }
    case "select_node":
      return { ...state, selectedNodeId: action.nodeId };
    case "clear_node":
      return { ...state, selectedNodeId: null };
    case "set_evidence_presentation":
      return { ...state, evidencePresentationOverride: action.presentation };
    case "close_overlay": {
      // The inspector is transient. Closing it should reveal the current beat's
      // default evidence presentation again, which may be a receipt.
      if (state.evidencePresentationOverride === "inspector") return { ...state, evidencePresentationOverride: null };
      if (state.selectedNodeId !== null) return { ...state, selectedNodeId: null };
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

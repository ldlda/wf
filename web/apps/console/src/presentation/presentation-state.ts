import {
  defaultMainLocation,
  findDiscussionBranch,
  findScene,
  type ChatMode,
  type ChatTheme,
  type DiscussionBranchId,
  type EvidenceMode,
  type MainLocation,
  type PresentationLocation,
  type StageTheme,
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
  readonly stageThemeOverride: StageTheme | null;
  readonly chatThemeOverride: ChatTheme | null;
  readonly chatModeOverride: ChatMode | null;
  readonly controlsOpen: boolean;
  readonly discussionIndexOpen: boolean;
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
  | { readonly type: "set_stage_theme"; readonly theme: StageTheme | null }
  | { readonly type: "set_chat_theme"; readonly theme: ChatTheme | null }
  | { readonly type: "set_chat_mode"; readonly mode: ChatMode | null }
  | { readonly type: "toggle_controls" }
  | { readonly type: "toggle_discussion_index" }
  | { readonly type: "toggle_motion" };

export const initialPresentationState: PresentationState = {
  location: defaultMainLocation,
  discussionReturn: null,
  selectedNodeId: null,
  evidenceModeOverride: null,
  playbackMode: "replay",
  stageThemeOverride: null,
  chatThemeOverride: null,
  chatModeOverride: null,
  controlsOpen: false,
  discussionIndexOpen: false,
  motionDisabled: false,
  startedAt: Date.now(),
};

const compositionForLocation = (
  location: PresentationLocation,
  evidenceOverride: EvidenceMode | null,
  stageThemeOverride: StageTheme | null,
  chatThemeOverride: ChatTheme | null,
  chatModeOverride: ChatMode | null,
): {
  readonly stageTheme: StageTheme;
  readonly chatTheme: ChatTheme;
  readonly chatMode: ChatMode;
  readonly evidenceMode: EvidenceMode;
} => {
  if (location.kind === "discussion") {
    const branch = findDiscussionBranch(location.branchId);
    const parentScene = branch ? findScene(branch.parentSceneId) : findScene("positioning");
    return {
      stageTheme: stageThemeOverride ?? parentScene?.stageTheme ?? "paper",
      chatTheme: chatThemeOverride ?? "dark",
      chatMode: chatModeOverride ?? "hidden",
      evidenceMode: evidenceOverride ?? "hidden",
    };
  }
  const scene = findScene(location.sceneId);
  const beat = scene?.beats.find((b) => b.id === location.beatId);
  return {
    stageTheme: stageThemeOverride ?? scene?.stageTheme ?? "paper",
    chatTheme: chatThemeOverride ?? beat?.chatTheme ?? "dark",
    chatMode: chatModeOverride ?? beat?.chatMode ?? "hidden",
    evidenceMode: evidenceOverride ?? beat?.evidenceMode ?? "hidden",
  };
};

export const compositionForState = (state: PresentationState) =>
  compositionForLocation(
    state.location,
    state.evidenceModeOverride,
    state.stageThemeOverride,
    state.chatThemeOverride,
    state.chatModeOverride,
  );

const isValidMainLocation = (location: PresentationLocation): location is MainLocation =>
  location.kind === "main";

const firstBeatOfScene = (sceneId: string): MainLocation | null => {
  const scene = findScene(sceneId);
  if (!scene || scene.beats.length === 0) return null;
  return { kind: "main", sceneId: scene.id as MainLocation["sceneId"], beatId: scene.beats[0]!.id };
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
      if (state.evidenceModeOverride !== null) return { ...state, evidenceModeOverride: null };
      const derivedEvidenceMode = (() => {
        if (state.location.kind === "discussion") return "hidden" as const;
        const scene = findScene(state.location.sceneId);
        const beat = scene?.beats.find((b) => b.id === (state.location as MainLocation).beatId);
        return beat?.evidenceMode ?? "hidden";
      })();
      if (derivedEvidenceMode !== "hidden") return { ...state, evidenceModeOverride: "hidden" };
      if (state.discussionIndexOpen) return { ...state, discussionIndexOpen: false };
      if (state.controlsOpen) return { ...state, controlsOpen: false };
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
    case "set_stage_theme":
      return { ...state, stageThemeOverride: action.theme };
    case "set_chat_theme":
      return { ...state, chatThemeOverride: action.theme };
    case "set_chat_mode":
      return { ...state, chatModeOverride: action.mode };
    case "toggle_controls":
      return { ...state, controlsOpen: !state.controlsOpen };
    case "toggle_discussion_index":
      return { ...state, discussionIndexOpen: !state.discussionIndexOpen };
    case "toggle_motion":
      return { ...state, motionDisabled: !state.motionDisabled };
  }
};

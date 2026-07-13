import {
  defaultMainLocation,
  findDiscussionBranch,
  findScene,
  mainScenes,
  type DiscussionLocation,
  type MainLocation,
  type PresentationLocation,
} from "./storyboard.js";

const flattenMainLocations = (): readonly MainLocation[] =>
  mainScenes.flatMap((scene) =>
    scene.beats.map((beat) => ({
      kind: "main" as const,
      sceneId: scene.id,
      beatId: beat.id,
      focusPath: beat.figure?.focusPath ?? [],
    })),
  );

const ROOT_FOCUS_SENTINEL = "~";

const authoredFocusPath = (sceneId: string, beatId: string): readonly string[] =>
  findScene(sceneId)?.beats.find((beat) => beat.id === beatId)?.figure?.focusPath ?? [];

export const hashForLocation = (location: PresentationLocation): string => {
  if (location.kind === "discussion") {
    return `#discuss/${encodeURIComponent(location.branchId)}`;
  }
  const base = `#scene/${encodeURIComponent(location.sceneId)}/${encodeURIComponent(location.beatId)}`;
  if (location.focusPath.length === 0) {
    // Beats may open on an authored nested figure. The sentinel preserves an
    // explicitly selected root view without making plain deep links ambiguous.
    return authoredFocusPath(location.sceneId, location.beatId).length > 0
      ? `${base}/focus/${ROOT_FOCUS_SENTINEL}`
      : base;
  }
  const segments = location.focusPath.map(encodeURIComponent).join("/");
  return `${base}/focus/${segments}`;
};

export const locationFromHash = (hash: string): PresentationLocation => {
  const raw = hash.replace(/^#/, "");
  const sceneMatch = raw.match(/^scene\/([^/]+)\/([^/]+)(?:\/focus\/(.*))?$/);
  if (sceneMatch) {
    let sceneId: string;
    let beatId: string;
    let focusPath: string[] = [];
    const sceneSegment = sceneMatch[1];
    const beatSegment = sceneMatch[2];
    const focusSegment = sceneMatch[3];
    if (!sceneSegment || !beatSegment) return defaultMainLocation;
    try {
      sceneId = decodeURIComponent(sceneSegment);
      beatId = decodeURIComponent(beatSegment);
      if (focusSegment === ROOT_FOCUS_SENTINEL) {
        focusPath = [];
      } else if (focusSegment !== undefined && focusSegment !== "") {
        focusPath = focusSegment.split("/").map(decodeURIComponent);
      }
    } catch {
      return defaultMainLocation;
    }
    const scene = findScene(sceneId);
    if (scene && scene.beats.some((b) => b.id === beatId)) {
      if (focusSegment === undefined) {
        focusPath = [...authoredFocusPath(scene.id, beatId)];
      }
      return { kind: "main", sceneId: scene.id as MainLocation["sceneId"], beatId, focusPath };
    }
    return defaultMainLocation;
  }
  const discussMatch = raw.match(/^discuss\/(.+)$/);
  if (discussMatch) {
    const branchSegment = discussMatch[1];
    if (!branchSegment) return defaultMainLocation;
    let branchId: string;
    try {
      branchId = decodeURIComponent(branchSegment);
    } catch {
      return defaultMainLocation;
    }
    if (findDiscussionBranch(branchId)) {
      return { kind: "discussion", branchId: branchId as DiscussionLocation["branchId"] };
    }
    return defaultMainLocation;
  }
  return defaultMainLocation;
};

export const nextMainLocation = (current: MainLocation): MainLocation => {
  const locations = flattenMainLocations();
  const index = locations.findIndex(
    (loc) => loc.sceneId === current.sceneId && loc.beatId === current.beatId,
  );
  if (index === -1 || index === locations.length - 1) return current;
  const next = locations[index + 1];
  return next ?? current;
};

export const previousMainLocation = (current: MainLocation): MainLocation => {
  const locations = flattenMainLocations();
  const index = locations.findIndex(
    (loc) => loc.sceneId === current.sceneId && loc.beatId === current.beatId,
  );
  if (index <= 0) return current;
  const prev = locations[index - 1];
  return prev ?? current;
};

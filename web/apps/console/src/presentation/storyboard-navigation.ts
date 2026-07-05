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

export const hashForLocation = (location: PresentationLocation): string => {
  if (location.kind === "discussion") {
    return `#discuss/${encodeURIComponent(location.branchId)}`;
  }
  const base = `#scene/${encodeURIComponent(location.sceneId)}/${encodeURIComponent(location.beatId)}`;
  if (location.focusPath.length === 0) return base;
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
    try {
      sceneId = decodeURIComponent(sceneMatch[1]!);
      beatId = decodeURIComponent(sceneMatch[2]!);
      if (sceneMatch[3] !== undefined && sceneMatch[3] !== "") {
        focusPath = sceneMatch[3]!.split("/").map(decodeURIComponent);
      }
    } catch {
      return defaultMainLocation;
    }
    const scene = findScene(sceneId);
    if (scene && scene.beats.some((b) => b.id === beatId)) {
      return { kind: "main", sceneId: scene.id as MainLocation["sceneId"], beatId, focusPath };
    }
    return defaultMainLocation;
  }
  const discussMatch = raw.match(/^discuss\/(.+)$/);
  if (discussMatch) {
    let branchId: string;
    try {
      branchId = decodeURIComponent(discussMatch[1]!);
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
  return locations[index + 1]!;
};

export const previousMainLocation = (current: MainLocation): MainLocation => {
  const locations = flattenMainLocations();
  const index = locations.findIndex(
    (loc) => loc.sceneId === current.sceneId && loc.beatId === current.beatId,
  );
  if (index <= 0) return current;
  return locations[index - 1]!;
};

import { locationFromHash, hashForLocation } from "../storyboard-navigation.js";
import { findDiscussionBranch, mainScenes, type DiscussionLocation, type MainLocation } from "../storyboard.js";
import { presenterBeatNoteFor, presenterNotes, type PresenterBeatNote } from "./presenter-notes.js";

export type PresenterLocation = MainLocation | DiscussionLocation;

export type PresenterNavigation = {
  readonly location: PresenterLocation;
  readonly note: PresenterBeatNote | null;
  readonly index: number;
  readonly previous: PresenterBeatNote | null;
  readonly next: PresenterBeatNote | null;
  readonly cumulativeSeconds: number;
};

const locationForNote = (note: PresenterBeatNote): MainLocation => ({
  kind: "main",
  sceneId: note.sceneId,
  beatId: note.beatId,
  focusPath: mainScenes.find((scene) => scene.id === note.sceneId)?.beats.find((beat) => beat.id === note.beatId)?.figure?.focusPath ?? [],
});

export const presenterHashForNote = (note: PresenterBeatNote): string => hashForLocation(locationForNote(note));

export const audienceHrefForNote = (note: PresenterBeatNote): string => `/present${presenterHashForNote(note)}`;

export const presenterNavigationFromHash = (hash: string): PresenterNavigation => {
  const parsed = locationFromHash(hash);
  if (parsed.kind === "discussion" && findDiscussionBranch(parsed.branchId)) {
    return { location: parsed, note: null, index: -1, previous: null, next: null, cumulativeSeconds: 0 };
  }

  const parsedNote = parsed.kind === "main" ? presenterBeatNoteFor(parsed.sceneId, parsed.beatId) : undefined;
  const note = parsedNote ?? presenterNotes[0];
  if (!note) throw new Error("presenter note catalog is empty");
  const index = presenterNotes.indexOf(note);
  return {
    location: locationForNote(note),
    note,
    index,
    previous: presenterNotes[index - 1] ?? null,
    next: presenterNotes[index + 1] ?? null,
    cumulativeSeconds: presenterNotes.slice(0, index + 1).reduce((total, item) => total + item.targetSeconds, 0),
  };
};

export const formatPresenterTime = (seconds: number): string => {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${minutes}:${remainder.toString().padStart(2, "0")}`;
};

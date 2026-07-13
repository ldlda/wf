import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { mainScenes } from "../storyboard.js";
import {
  completeDeckTargetSeconds,
  discussionBranchForId,
  mainSpeechWordCount,
  presenterBeatNoteFor,
  presenterNotes,
  presenterSceneNotes,
} from "./presenter-notes.js";

describe("presenter note catalog", () => {
  it("has exactly one note for every current storyboard beat", () => {
    const noteKeys = presenterNotes.map((note) => `${note.sceneId}/${note.beatId}`);

    expect(new Set(noteKeys).size).toBe(noteKeys.length);
    for (const scene of mainScenes) {
      for (const beat of scene.beats) {
        const note = presenterBeatNoteFor(scene.id, beat.id);
        expect(note).toBeDefined();
        expect(note?.mustSay.trim().length).toBeGreaterThan(0);
      }
    }

    expect(noteKeys).toHaveLength(mainScenes.flatMap((scene) => scene.beats).length);
  });

  it("keeps the planned scene timing and complete-deck cap", () => {
    expect(mainScenes.map((scene) => presenterSceneNotes(scene.id).reduce((sum, note) => sum + note.targetSeconds, 0))).toEqual([
      45,
      45,
      45,
      55,
      45,
      41,
      20,
      54,
      35,
      30,
      50,
      120,
      75,
    ]);
    expect(completeDeckTargetSeconds()).toBe(735);
    expect(completeDeckTargetSeconds()).toBeLessThanOrEqual(780);
  });

  it("keeps NodeUse out of timed notes while retaining the architecture spine", () => {
    expect(presenterBeatNoteFor("architecture", "node-use")).toBeUndefined();
    expect(presenterBeatNoteFor("architecture", "overview")).toBeDefined();
    expect(presenterBeatNoteFor("architecture", "api")).toBeDefined();
    expect(presenterBeatNoteFor("architecture", "runtime")).toBeDefined();
  });

  it("keeps the must-say speech within the defense word budget", () => {
    expect(mainSpeechWordCount()).toBeGreaterThanOrEqual(750);
    expect(mainSpeechWordCount()).toBeLessThanOrEqual(850);
  });

  it("keeps the readable speech runbook synchronized with every must-say note", () => {
    const speech = readFileSync(
      join(import.meta.dirname, "../../../../../../docs/runbooks/defense-speech-and-claim-audit.md"),
      "utf8",
    );

    for (const note of presenterNotes) {
      // Markdown emphasis is presenter-only typography; the runbook stores the
      // same spoken words without requiring identical inline formatting.
      const spokenText = note.mustSay.replaceAll("**", "");
      expect(speech, `${note.sceneId}/${note.beatId}`).toContain(spokenText);
    }
  });

  it("requires evidence and resolvable Q&A links without empty placeholders", () => {
    for (const note of presenterNotes) {
      expect(note.evidencePointers.length).toBeGreaterThan(0);
      for (const pointer of note.evidencePointers) {
        expect(pointer.trim().length).toBeGreaterThan(0);
      }
      for (const branchId of note.qnaBranchIds) {
        expect(discussionBranchForId(branchId)).toBeDefined();
      }
      for (const optionalField of [note.optionalDetail, note.warning, note.fallback]) {
        expect(optionalField === null || optionalField.trim().length > 0).toBe(true);
      }
    }
  });
});

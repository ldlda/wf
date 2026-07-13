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
    const canonicalKeys = mainScenes.flatMap((scene) => scene.beats.map((beat) => `${scene.id}/${beat.id}`));

    expect(new Set(noteKeys).size).toBe(noteKeys.length);
    expect([...noteKeys].sort()).toEqual([...canonicalKeys].sort());
    for (const scene of mainScenes) {
      for (const beat of scene.beats) {
        const note = presenterBeatNoteFor(scene.id, beat.id);
        expect(note).toBeDefined();
        expect(note?.mustSay.trim().length).toBeGreaterThan(0);
      }
    }

    expect(noteKeys).toHaveLength(canonicalKeys.length);
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
    expect(completeDeckTargetSeconds()).toBeLessThanOrEqual(900);
    expect(presenterSceneNotes("prepared-lifecycle")).toHaveLength(6);
    for (const note of presenterSceneNotes("prepared-lifecycle")) {
      expect(note.targetSeconds).toBeGreaterThanOrEqual(8);
      expect(note.targetSeconds).toBeLessThanOrEqual(10);
    }
  });

  it("keeps removed scene and beat IDs out of timed notes", () => {
    expect(presenterNotes.some((note) => note.sceneId === ("authoring" as typeof mainScenes[number]["id"]))).toBe(false);
    expect(presenterBeatNoteFor("prepared-lifecycle", "validate")).toBeUndefined();
    expect(presenterBeatNoteFor("architecture", "node-use")).toBeUndefined();
  });

  it("describes structured diagnosis and the focused output-map repair", () => {
    expect(presenterBeatNoteFor("prepared-lifecycle", "diagnose")?.mustSay).toMatch(/structured diagnostics/i);
    expect(presenterBeatNoteFor("prepared-lifecycle", "repair")?.mustSay).toMatch(/focused output-map edit/i);
  });

  it("keeps NodeUse out of timed notes while retaining the architecture spine", () => {
    expect(presenterBeatNoteFor("architecture", "overview")).toBeDefined();
    expect(presenterBeatNoteFor("architecture", "api")).toBeDefined();
    expect(presenterBeatNoteFor("architecture", "runtime")).toBeDefined();
  });

  it("keeps the must-say speech within the defense word budget", () => {
    expect(mainSpeechWordCount()).toBeGreaterThanOrEqual(650);
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

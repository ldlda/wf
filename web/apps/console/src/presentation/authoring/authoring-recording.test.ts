import { describe, expect, it } from "vitest";
import {
  authoringPhaseForBeat,
  projectPreparedAuthoring,
  type AuthoringPhaseId,
} from "./authoring-recording.js";

describe("authoringPhaseForBeat", () => {
  it("returns all five phases in order", () => {
    const phases: readonly AuthoringPhaseId[] = [
      "discover",
      "draft",
      "validate",
      "artifact",
      "deployment",
    ];
    for (const phase of phases) {
      expect(authoringPhaseForBeat(phase)).toBe(phase);
    }
  });

  it("maps beat IDs to expected phases", () => {
    expect(authoringPhaseForBeat("discover")).toBe("discover");
    expect(authoringPhaseForBeat("draft")).toBe("draft");
    expect(authoringPhaseForBeat("validate")).toBe("validate");
    expect(authoringPhaseForBeat("artifact")).toBe("artifact");
    expect(authoringPhaseForBeat("deployment")).toBe("deployment");
  });

  it("throws for unknown beat IDs", () => {
    expect(() => authoringPhaseForBeat("unknown" as AuthoringPhaseId)).toThrow("unknown phase");
  });
});

describe("projectPreparedAuthoring", () => {
  it("returns all five phases in order", () => {
    const phases = projectPreparedAuthoring();
    expect(phases.map((p) => p.phase)).toEqual([
      "discover",
      "draft",
      "validate",
      "artifact",
      "deployment",
    ]);
  });

  it("includes at least one user turn in the recording", () => {
    const phases = projectPreparedAuthoring();
    const allMessages = phases.flatMap((p) => p.conversation);
    const userTurns = allMessages.filter((m) => m.role === "user");
    expect(userTurns.length).toBeGreaterThanOrEqual(1);
  });

  it("includes at least two assistant turns total", () => {
    const phases = projectPreparedAuthoring();
    const allMessages = phases.flatMap((p) => p.conversation);
    const assistantTurns = allMessages.filter((m) => m.role === "assistant");
    expect(assistantTurns.length).toBeGreaterThanOrEqual(2);
  });

  it("has at least two commands per phase", () => {
    const phases = projectPreparedAuthoring();
    for (const phase of phases) {
      expect(phase.commands.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("starts every command with wf or uv run wf", () => {
    const phases = projectPreparedAuthoring();
    for (const phase of phases) {
      for (const cmd of phase.commands) {
        expect(cmd.command.startsWith("wf") || cmd.command.startsWith("uv run wf")).toBe(true);
      }
    }
  });

  it("has unique beat IDs for each phase", () => {
    const phases = projectPreparedAuthoring();
    const ids = phases.map((p) => p.beatId);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

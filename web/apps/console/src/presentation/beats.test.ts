import { describe, expect, it } from "vitest";
import { beatFromHash, hashForBeat, presentationBeats } from "./beats.js";

describe("presentation beats", () => {
  it("has stable unique beat ids", () => {
    const ids = presentationBeats.map((beat) => beat.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toEqual([
      "intro",
      "chat-request",
      "tool-call-start",
      "graph-reveal",
      "interrupt-approval",
      "resume-output",
      "trace-evidence",
      "boundary-wrap",
    ]);
  });

  it("maps beats to hash fragments and falls back to intro", () => {
    expect(hashForBeat("interrupt-approval")).toBe("#interrupt-approval");
    expect(beatFromHash("#interrupt-approval")).toBe("interrupt-approval");
    expect(beatFromHash("#missing")).toBe("intro");
    expect(beatFromHash("")).toBe("intro");
  });
});

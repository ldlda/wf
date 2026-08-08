import { describe, expect, it } from "vitest";
import { formatBoundedJson } from "./format-bounded-json.js";

describe("formatBoundedJson", () => {
  it("bounds traversal without reading remote fields after the budget", () => {
    const draft = {
      first: "x".repeat(1_000),
      get later() {
        throw new Error("later field should not be read");
      },
    };

    expect(() => formatBoundedJson(draft, 80)).not.toThrow();
    expect(formatBoundedJson(draft, 80)).toHaveLength(80);
    expect(formatBoundedJson(draft, 80)).toContain("truncated");
  });

  it("keeps an exact-fit JSON document complete and valid", () => {
    const draft = { step: "collect", count: 2 };
    const completeJson = JSON.stringify(draft, null, 2);

    expect(formatBoundedJson(draft, completeJson.length)).toBe(completeJson);
    expect(JSON.parse(formatBoundedJson(draft, completeJson.length))).toEqual(draft);
  });

  it("does not truncate a complete document just below the boundary", () => {
    const draft = { step: "collect", count: 2 };
    const completeJson = JSON.stringify(draft, null, 2);

    expect(formatBoundedJson(draft, completeJson.length + 1)).toBe(completeJson);
    expect(formatBoundedJson(draft, completeJson.length - 1)).toContain("truncated");
  });
});

import { describe, expect, it } from "vitest";
import type { DraftDiagnostic } from "../domain/draft-workspace-models.js";
import { withDiagnosticKeys } from "./diagnostic-key.js";

const diagnostic = (overrides: Partial<DraftDiagnostic> = {}): DraftDiagnostic => ({
  code: "missing_route",
  path: "routes.review",
  message: "Review needs a route.",
  stepId: "review",
  repairHint: "Add a submitted route.",
  details: {},
  ...overrides,
});

describe("withDiagnosticKeys", () => {
  it("collapses exact duplicates while preserving distinct diagnostics and order", () => {
    const first = diagnostic();
    const second = diagnostic({ code: "invalid_step" });

    const entries = withDiagnosticKeys([first, first, second, first]);

    expect(entries).toHaveLength(2);
    expect(entries.map(({ diagnostic: entryDiagnostic }) => entryDiagnostic)).toEqual([
      first,
      second,
    ]);
    expect(entries[0]?.key).toBe(withDiagnosticKeys([first])[0]?.key);
  });

  it("keeps distinct diagnostic keys stable across insertion and reorder", () => {
    const review = diagnostic();
    const invalid = diagnostic({ code: "invalid_step" });
    const start = diagnostic({ code: "missing_start" });
    const initial = withDiagnosticKeys([review, invalid]);
    const reordered = withDiagnosticKeys([start, invalid, review]);

    const keyFor = (
      entries: ReturnType<typeof withDiagnosticKeys>,
      code: string,
    ): string | undefined => entries.find(({ diagnostic: entryDiagnostic }) => entryDiagnostic.code === code)?.key;

    expect(keyFor(reordered, review.code)).toBe(keyFor(initial, review.code));
    expect(keyFor(reordered, invalid.code)).toBe(keyFor(initial, invalid.code));
    expect(reordered.map(({ diagnostic: entryDiagnostic }) => entryDiagnostic.code)).toEqual([
      start.code,
      invalid.code,
      review.code,
    ]);
  });

  it("keeps diagnostics distinct when details, step, or hint differ", () => {
    const withDifferentDetails = diagnostic({ details: { field: "title" } });
    const withOtherDetails = diagnostic({ details: { field: "name" } });
    const withDifferentStep = diagnostic({ stepId: "collect" });
    const withDifferentHint = diagnostic({ repairHint: "Choose another route." });

    const entries = withDiagnosticKeys([
      withDifferentDetails,
      withOtherDetails,
      withDifferentStep,
      withDifferentHint,
    ]);

    expect(entries).toHaveLength(4);
    expect(new Set(entries.map(({ key }) => key)).size).toBe(4);
    expect(entries.map(({ diagnostic: entryDiagnostic }) => entryDiagnostic)).toEqual([
      withDifferentDetails,
      withOtherDetails,
      withDifferentStep,
      withDifferentHint,
    ]);
  });

  it("deduplicates equivalent nested details regardless of object key order", () => {
    const left = diagnostic({ details: { field: "title", context: { row: 1, source: "input" } } });
    const right = diagnostic({ details: { context: { source: "input", row: 1 }, field: "title" } });

    expect(withDiagnosticKeys([left, right])).toHaveLength(1);
  });
});

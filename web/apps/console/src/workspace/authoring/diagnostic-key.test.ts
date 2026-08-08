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
  it("keeps unchanged diagnostic keys stable when another diagnostic is inserted", () => {
    const first = withDiagnosticKeys([diagnostic(), diagnostic({ code: "invalid_step" })]);
    const second = withDiagnosticKeys([
      diagnostic({ code: "missing_start" }),
      diagnostic(),
      diagnostic({ code: "invalid_step" }),
    ]);

    expect(second[1]?.key).toBe(first[0]?.key);
    expect(second[2]?.key).toBe(first[1]?.key);
  });

  it("gives duplicate diagnostics distinct stable occurrence keys", () => {
    const entries = withDiagnosticKeys([diagnostic(), diagnostic()]);

    expect(entries[0]?.key).not.toBe(entries[1]?.key);
    expect(entries[0]?.key).toBe(withDiagnosticKeys([diagnostic()])[0]?.key);
  });
});

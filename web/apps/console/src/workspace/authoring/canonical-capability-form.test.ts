import { describe, expect, it } from "vitest";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { canonicalCapabilityFormData } from "./canonical-capability-form.js";

const draft = (step: Record<string, unknown>): DraftWorkspace => ({
  workspaceId: "draft-report",
  revision: 1,
  title: "Report",
  status: "valid",
  diagnostics: [],
  summary: {
    name: "report",
    start: "render",
    stepCount: 1,
    routeCount: 0,
    steps: ["render"],
  },
  draft: { steps: { render: step } },
});

describe("canonical capability form projection", () => {
  it("preserves absent setup metadata instead of converting it to null", () => {
    const projected = canonicalCapabilityFormData(draft({ use: "wf.std.concat", retry: 0 }), "render");

    expect(projected?.initialValue).toEqual({ stepId: "render", retry: 0 });
    expect(projected?.initialValue).not.toHaveProperty("description");
    expect(projected?.initialValue).not.toHaveProperty("timeoutSeconds");
  });

  it("preserves explicit null setup metadata", () => {
    const projected = canonicalCapabilityFormData(
      draft({ use: "wf.std.concat", desc: null, retry: null, timeout_seconds: null }),
      "render",
    );

    expect(projected?.initialValue).toEqual({
      stepId: "render",
      description: null,
      retry: null,
      timeoutSeconds: null,
    });
  });

  it("ignores negative and sparse array targets instead of creating array properties", () => {
    const projected = canonicalCapabilityFormData(
      draft({
        use: "wf.std.concat",
        input: [
          { target: { root: "local", parts: ["items", "-1"] }, value: "negative" },
          { target: { root: "local", parts: ["items", "2"] }, value: "sparse" },
        ],
      }),
      "render",
    );

    expect(projected?.initialInputValue).toEqual({ items: [] });
  });
});

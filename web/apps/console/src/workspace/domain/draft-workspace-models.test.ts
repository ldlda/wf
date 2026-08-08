import { describe, expect, it } from "vitest";
import {
  decodeDraftWorkspace,
  decodeDraftWorkspacePage,
  type AddCapabilityStepInput,
  type CreateEmptyDraftInput,
  type InputBinding,
} from "./draft-workspace-models.js";

const summary = {
  name: { preserved: true },
  start: ["opaque", 1],
  stepCount: 1,
  routeCount: 0,
  steps: ["read"],
};

describe("draft workspace models", () => {
  it("requires canonical path or value binding shapes", () => {
    const canonicalBinding = {
      target: "text",
      path: "input.text",
    } satisfies InputBinding;

    const invalidInput: AddCapabilityStepInput = {
      workspaceId: "draft-report",
      revision: 1,
      stepId: "read",
      capabilityName: "demo.read",
      // @ts-expect-error Binding payloads must use canonical path/value keys.
      inputBindings: [{ sourcePath: "input.text", targetPath: "text" }],
    };

    expect(canonicalBinding).toEqual({ target: "text", path: "input.text" });
    expect(invalidInput).toBeDefined();
  });

  it("exposes camelCase inputs for draft authoring", () => {
    const emptyInput = {
      workspaceId: "draft-report",
      name: "report",
    } satisfies CreateEmptyDraftInput;
    const stepInput = {
      workspaceId: "draft-report",
      revision: 1,
      stepId: "read",
      capabilityName: "demo.read",
    } satisfies AddCapabilityStepInput;

    expect(emptyInput.workspaceId).toBe("draft-report");
    expect(stepInput.capabilityName).toBe("demo.read");
  });

  it("preserves opaque summary values and defaults an omitted draft", () => {
    const workspace = decodeDraftWorkspace({
      workspaceId: "draft-report",
      revision: 3,
      title: null,
      status: "valid",
      diagnostics: [],
      summary,
    });

    expect(workspace.summary.name).toEqual({ preserved: true });
    expect(workspace.summary.start).toEqual(["opaque", 1]);
    expect(workspace.draft).toBeNull();
  });

  it("decodes a page with an optional draft document", () => {
    const page = decodeDraftWorkspacePage({
      items: [
        {
          workspaceId: "draft-report",
          revision: 1,
          title: "Report",
          status: "invalid",
          diagnostics: [],
          summary,
          draft: { nodes: [] },
        },
      ],
    });

    expect(page.items[0]?.draft).toEqual({ nodes: [] });
  });

  it("rejects a malformed diagnostic", () => {
    expect(() =>
      decodeDraftWorkspace({
        workspaceId: "draft-report",
        revision: 1,
        title: "Report",
        status: "invalid",
        diagnostics: [{ code: "missing-path" }],
        summary,
      }),
    ).toThrow(/DraftWorkspace is malformed/);
  });
});

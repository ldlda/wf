import { describe, expect, it } from "vitest";
import {
  decodeDraftWorkspace,
  decodeDraftWorkspacePage,
} from "./draft-workspace-models.js";

const summary = {
  name: { preserved: true },
  start: ["opaque", 1],
  stepCount: 1,
  routeCount: 0,
  steps: ["read"],
};

describe("draft workspace models", () => {
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

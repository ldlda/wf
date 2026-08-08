import { describe, expect, it, vi } from "vitest";
import {
  decodeDraftWorkspace,
  decodeDraftWorkspacePage,
} from "./draft-workspace-models.js";
import { createDraftWorkspaceClient } from "./draft-workspace-client.js";
import type { ConsoleReadExecutor } from "./read-executor.js";

const executor = () =>
  ({ run: vi.fn().mockResolvedValue({}) }) as unknown as ConsoleReadExecutor;

describe("DraftWorkspaceClient", () => {
  it("lists draft workspaces without a mutation payload", async () => {
    const readExecutor = executor();
    const client = createDraftWorkspaceClient(readExecutor);

    await client.list();

    expect(readExecutor.run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.list",
      {},
      decodeDraftWorkspacePage,
    );
  });

  it("loads a draft with the full document enabled", async () => {
    const readExecutor = executor();
    const client = createDraftWorkspaceClient(readExecutor);

    await client.load("  draft-report  ");

    expect(readExecutor.run).toHaveBeenCalledWith(
      "workflow.draft_workspaces.get",
      { workspace_id: "draft-report", include_draft: true },
      decodeDraftWorkspace,
    );
  });

  it("rejects blank workspace identifiers before invoking the executor", async () => {
    const readExecutor = executor();
    const client = createDraftWorkspaceClient(readExecutor);

    await expect(client.load(" \t")).rejects.toMatchObject({
      kind: "operation",
      operation: "workflow.draft_workspaces.get",
    });
    expect(readExecutor.run).not.toHaveBeenCalled();
  });
});

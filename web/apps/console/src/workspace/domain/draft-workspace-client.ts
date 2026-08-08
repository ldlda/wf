import type { OperationName } from "../../connection/contracts.js";
import {
  decodeDraftWorkspace,
  decodeDraftWorkspacePage,
  type DraftWorkspace,
  type DraftWorkspacePage,
} from "./draft-workspace-models.js";
import { ConsoleClientError } from "./errors.js";
import type { ConsoleReadExecutor } from "./read-executor.js";

export interface DraftWorkspaceClient {
  list(): Promise<DraftWorkspacePage>;
  load(workspaceId: string): Promise<DraftWorkspace>;
}

const invalidInput = (operation: OperationName, message: string): ConsoleClientError =>
  new ConsoleClientError("operation", operation, message);

export const createDraftWorkspaceClient = (
  executor: ConsoleReadExecutor,
): DraftWorkspaceClient => ({
  list: () =>
    executor.run(
      "workflow.draft_workspaces.list",
      {},
      decodeDraftWorkspacePage,
    ),

  load: (workspaceId) => {
    const normalizedWorkspaceId = workspaceId.trim();
    if (!normalizedWorkspaceId) {
      return Promise.reject(
        invalidInput(
          "workflow.draft_workspaces.get",
          "workspace id must not be blank",
        ),
      );
    }
    return executor.run(
      "workflow.draft_workspaces.get",
      { workspace_id: normalizedWorkspaceId, include_draft: true },
      decodeDraftWorkspace,
    );
  },
});

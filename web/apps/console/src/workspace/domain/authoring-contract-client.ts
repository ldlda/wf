import type { OperationName } from "../../connection/contracts.js";
import {
  decodeAuthoringContractInventory,
  type AuthoringContractInventory,
} from "./authoring-contract-models.js";
import { ConsoleClientError } from "./errors.js";
import type { ConsoleReadExecutor } from "./read-executor.js";

export type AuthoringContractInspectionInput = {
  readonly workspaceId: string;
  readonly revision: number;
  readonly selectedStepId?: string | null;
};

export interface AuthoringContractClient {
  inspect(input: AuthoringContractInspectionInput): Promise<AuthoringContractInventory>;
}

const invalidInput = (operation: OperationName, message: string): ConsoleClientError =>
  new ConsoleClientError("operation", operation, message);

export const createAuthoringContractClient = (
  executor: ConsoleReadExecutor,
): AuthoringContractClient => ({
  inspect: async (input) => {
    const workspaceId = input.workspaceId.trim();
    if (!workspaceId) {
      throw invalidInput(
        "workflow.draft_workspaces.inspect_authoring_contract",
        "workspace id must not be blank",
      );
    }
    const selectedStepId = input.selectedStepId?.trim() || null;
    const inventory = await executor.run(
      "workflow.draft_workspaces.inspect_authoring_contract",
      {
        workspace_id: workspaceId,
        revision: input.revision,
        selected_step_id: selectedStepId,
      },
      decodeAuthoringContractInventory,
    );
    if (
      inventory.workspaceId !== workspaceId ||
      inventory.revision !== input.revision
    ) {
      throw new Error("authoring contract response does not match inspection request");
    }
    return inventory;
  },
});

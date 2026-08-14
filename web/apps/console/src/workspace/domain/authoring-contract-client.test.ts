import { describe, expect, it } from "vitest";
import type { OperationName } from "../../connection/contracts.js";
import {
  decodeAuthoringContractInventory,
} from "./authoring-contract-models.js";
import { createAuthoringContractClient } from "./authoring-contract-client.js";
import type { ConsoleReadExecutor } from "./read-executor.js";

const wireInventory = {
  workspace_id: "draft-report",
  revision: 7,
  selected_step_id: null,
  readable_sources: [],
  step_input_targets: [],
  step_output_sources: [],
  state_targets: [],
  workflow_output_targets: [],
  entry_steps: [],
  workflow_outcomes: ["ok"],
  warnings: [],
};

type RunCall = {
  readonly operation: OperationName;
  readonly params: unknown;
  readonly decode: (value: unknown) => unknown;
};

const runWith = (
  response: unknown,
): { readonly executor: ConsoleReadExecutor; readonly calls: RunCall[] } => {
  const calls: RunCall[] = [];
  const run: ConsoleReadExecutor["run"] = async <T>(
    operation: OperationName,
    params: unknown,
    decode: (value: unknown) => T,
  ): Promise<T> => {
    calls.push({ operation, params, decode });
    return decode(response);
  };
  return { executor: { run }, calls };
};

describe("AuthoringContractClient", () => {
  it("sends the exact inspection params and decodes the response", async () => {
    const { executor, calls } = runWith(wireInventory);
    const client = createAuthoringContractClient(executor);

    const result = await client.inspect({
      workspaceId: "  draft-report ",
      revision: 7,
      selectedStepId: "render",
    });

    expect(calls[0]?.operation).toBe("workflow.draft_workspaces.inspect_authoring_contract");
    expect(calls[0]?.params).toEqual({
      workspace_id: "draft-report",
      revision: 7,
      selected_step_id: "render",
    });
    expect(calls[0]?.decode).toBe(decodeAuthoringContractInventory);
    expect(result.workspaceId).toBe("draft-report");
  });

  it("passes null when no step is selected", async () => {
    const { executor, calls } = runWith(wireInventory);
    const client = createAuthoringContractClient(executor);

    await client.inspect({ workspaceId: "draft-report", revision: 7, selectedStepId: null });

    expect(calls[0]?.operation).toBe("workflow.draft_workspaces.inspect_authoring_contract");
    expect(calls[0]?.params).toEqual({
      workspace_id: "draft-report",
      revision: 7,
      selected_step_id: null,
    });
    expect(calls[0]?.decode).toBe(decodeAuthoringContractInventory);
  });

  it.each([
    ["workspaceId", { workspace_id: "other" }],
    ["revision", { revision: 8 }],
  ])("rejects a response with a mismatched %s", async (_field, replacement) => {
    const { executor } = runWith({ ...wireInventory, ...replacement });
    const client = createAuthoringContractClient(executor);

    await expect(
      client.inspect({ workspaceId: "draft-report", revision: 7, selectedStepId: null }),
    ).rejects.toThrow("does not match inspection request");
  });
});

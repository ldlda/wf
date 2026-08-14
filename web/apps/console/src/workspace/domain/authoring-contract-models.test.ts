import { describe, expect, it } from "vitest";
import {
  decodeAuthoringContractInventory,
  type AuthoringContractInventory,
} from "./authoring-contract-models.js";

const pathOption = {
  path: "input.title",
  label: "Title",
  origin: "workflow_input",
  schema: { type: "string", description: "A report title." },
  required: true,
  availability: "available",
  uses: ["step_input", "workflow_output"],
  description: "A report title.",
};

const inventory = {
  workspace_id: "draft-report",
  revision: 7,
  selected_step_id: "render",
  readable_sources: [pathOption],
  step_input_targets: [
    {
      ...pathOption,
      path: "step_input.title",
      origin: "step_input",
      uses: ["step_input"],
    },
  ],
  step_output_sources: [
    {
      ...pathOption,
      path: "step_output.markdown",
      origin: "step_output",
      uses: ["step_output_source"],
    },
  ],
  state_targets: [
    {
      ...pathOption,
      path: "state.report",
      origin: "workflow_state",
      uses: ["state_target", "workflow_output"],
    },
  ],
  workflow_output_targets: [
    {
      ...pathOption,
      path: "output.report",
      origin: "workflow_output",
      uses: ["workflow_output"],
    },
  ],
  entry_steps: [
    {
      step_id: "render",
      label: "Render report",
      description: "Render the report.",
      input_targets: [],
      output_sources: [],
      outcomes: ["ok", "error"],
    },
  ],
  workflow_outcomes: ["ok", "error"],
  warnings: ["Context is conditional."],
} satisfies Record<string, unknown>;

describe("authoring contract models", () => {
  it("decodes the complete inventory into camelCase browser fields", () => {
    const decoded = decodeAuthoringContractInventory(inventory);

    expect(decoded.workspaceId).toBe("draft-report");
    expect(decoded.selectedStepId).toBe("render");
    expect(decoded.readableSources[0]?.origin).toBe("workflow_input");
    expect(decoded.readableSources[0]?.schema).toEqual(pathOption.schema);
    expect(decoded.stepInputTargets[0]?.path).toBe("step_input.title");
    expect(decoded.entrySteps[0]?.stepId).toBe("render");
    expect(decoded.entrySteps[0]?.inputTargets).toEqual([]);
  });

  it.each([
    ["origin", { origin: "unknown" }],
    ["availability", { availability: "maybe" }],
    ["use", { uses: ["unknown"] }],
    ["schema", { schema: "not an object" }],
  ])("rejects an unknown or malformed path option %s", (_field, replacement) => {
    const malformed = {
      ...inventory,
      readable_sources: [{ ...pathOption, ...replacement }],
    };

    expect(() => decodeAuthoringContractInventory(malformed)).toThrow(
      "AuthoringContractInventory is malformed",
    );
  });

  it("rejects a malformed inventory envelope", () => {
    expect(() => decodeAuthoringContractInventory({ ...inventory, revision: "7" })).toThrow(
      "AuthoringContractInventory is malformed",
    );
  });

  const _typeCheck: AuthoringContractInventory | null = null;
  void _typeCheck;
});

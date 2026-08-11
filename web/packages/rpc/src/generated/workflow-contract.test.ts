import { describe, expect, expectTypeOf, it } from "vitest";
import {
  isOperationName,
  listOperations,
  WorkflowRpcs,
  workflowRpcOperationNames,
  workflowOperationNames,
  type OperationName,
  type WorkflowOperationParams,
  type WorkflowOperationResult,
} from "../index.js";

describe("generated workflow contract", () => {
  it("contains every operation exactly once", () => {
    expect(workflowOperationNames).toHaveLength(70);
    expect(new Set(workflowOperationNames)).toHaveLength(70);
  });

  it("contains every authored Effect operation without broadening its boundary", () => {
    const generatedNames = new Set<string>(workflowOperationNames);
    const supportedNames = listOperations().map(({ method }) => method);
    const expectedMethods = [
      "workflow.health",
      "workflow.sources.list",
      "workflow.capabilities.list",
      "workflow.capabilities.inspect",
      "workflow.capabilities.call",
      "workflow.draft_workspaces.list",
      "workflow.draft_workspaces.get",
      "workflow.draft_workspaces.create_empty",
      "workflow.draft_workspaces.create_from_capability",
      "workflow.draft_workspaces.add_step_from_capability",
      "workflow.draft_workspaces.update_capability_step",
      "workflow.draft_workspaces.set_route",
      "workflow.draft_workspaces.set_step_input_bindings",
      "workflow.draft_workspaces.set_step_output_bindings",
      "workflow.draft_workspaces.validate",
      "workflow.artifacts.list",
      "workflow.artifacts.inspect",
      "workflow.deployments.list",
      "workflow.deployments.inspect",
      "workflow.deployments.validate",
      "workflow.runs.list",
      "workflow.runs.inspect",
      "workflow.runs.start",
      "workflow.runs.resume",
      "workflow.runs.trace",
    ];

    expect(supportedNames).toHaveLength(expectedMethods.length);
    expect(supportedNames).toEqual(expectedMethods);
    expect(supportedNames.every((method) => generatedNames.has(method))).toBe(true);
    expect(workflowRpcOperationNames).toEqual(supportedNames);
    expect(workflowRpcOperationNames).toEqual(
      Array.from(WorkflowRpcs.requests.keys()),
    );
    expect(isOperationName("workflow.health")).toBe(true);
    expect(isOperationName("workflow.admin.auth.list")).toBe(false);
    expectTypeOf<OperationName>().toEqualTypeOf<
      (typeof workflowRpcOperationNames)[number]
    >();
  });

  it("exposes operation-specific raw parameter and result types", () => {
    expectTypeOf<WorkflowOperationParams<"workflow.health">>().toEqualTypeOf<
      Record<string, never>
    >();
    expectTypeOf<WorkflowOperationParams<"workflow.runs.start">>().toMatchTypeOf<{
      deployment_id: string;
      trace_range?: unknown;
      workflow_input?: { [key: string]: unknown };
    }>();
    expectTypeOf<WorkflowOperationResult<"workflow.health">>().toMatchTypeOf<{
      status: "ok";
      store_root: string;
    }>();
  });
});

import { describe, expect, expectTypeOf, it } from "vitest";
import {
  listOperations,
  workflowOperationNames,
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

    expect(supportedNames).toHaveLength(12);
    expect(supportedNames.every((method) => generatedNames.has(method))).toBe(true);
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

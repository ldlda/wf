import { Either, Schema } from "effect";
import { describe, expect, it } from "vitest";
import type {
  WorkflowOperationParams,
  WorkflowOperationResult,
} from "../generated/workflow-contract.js";
import { workflowRuntimeContract } from "../generated/workflow-contract.js";
import { runtimeSchemasFor } from "./runtime-schema.js";

const accepts = (schema: Schema.Schema.AnyNoContext, value: unknown): boolean =>
  Either.isRight(
    Schema.decodeUnknownEither(schema)(value, { onExcessProperty: "error" }),
  );

describe("runtimeSchemasFor", () => {
  it("contains exactly the parity-clean authored RPC cohort", () => {
    expect(Object.keys(workflowRuntimeContract.operations)).toEqual([
      "workflow.artifacts.inspect",
      "workflow.artifacts.list",
      "workflow.deployments.inspect",
      "workflow.deployments.list",
      "workflow.deployments.validate",
      "workflow.health",
      "workflow.runs.list",
      "workflow.sources.list",
    ]);
  });

  it("returns typed payload and result schemas for a generated operation", () => {
    const schemas = runtimeSchemasFor("workflow.health");
    const payload: WorkflowOperationParams<"workflow.health"> =
      Schema.decodeUnknownSync(schemas.payload)({});
    const result: WorkflowOperationResult<"workflow.health"> =
      Schema.decodeUnknownSync(schemas.success)({
        status: "ok",
        store_root: "C:/store",
      });

    expect(payload).toEqual({});
    expect(result.status).toBe("ok");
    expect(accepts(schemas.success, { status: "bad", store_root: "C:/store" })).toBe(
      false,
    );
  });

  it("keeps generated payload constraints at runtime", () => {
    const schemas = runtimeSchemasFor("workflow.sources.list");

    expect(accepts(schemas.payload, { limit: 100 })).toBe(true);
    expect(accepts(schemas.payload, { limit: 101 })).toBe(false);
    expect(accepts(schemas.payload, { extra: true })).toBe(false);
  });

  it("rejects adversarial nesting before recursive JSON decoding", () => {
    const schemas = runtimeSchemasFor("workflow.artifacts.inspect");
    let plan: unknown = "leaf";
    for (let depth = 0; depth < 70; depth += 1) plan = { nested: plan };

    expect(
      accepts(schemas.success, {
        id: "report",
        version: 1,
        title: "Report",
        kind: "workflow",
        description: null,
        outcomes: [],
        input_schema: {},
        output_schema: {},
        plan,
        required_capabilities: [],
        workflow_dependencies: {},
        created_from_catalog_version: null,
      }),
    ).toBe(false);
  });
});

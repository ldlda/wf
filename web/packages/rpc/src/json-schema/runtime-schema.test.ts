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
  it("contains exactly the authored RPC cohort", () => {
    expect(Object.keys(workflowRuntimeContract.operations)).toEqual([
      "workflow.artifacts.inspect",
      "workflow.artifacts.list",
      "workflow.capabilities.inspect",
      "workflow.capabilities.list",
      "workflow.deployments.inspect",
      "workflow.deployments.list",
      "workflow.deployments.validate",
      "workflow.draft_workspaces.get",
      "workflow.draft_workspaces.list",
      "workflow.health",
      "workflow.runs.inspect",
      "workflow.runs.list",
      "workflow.runs.resume",
      "workflow.runs.start",
      "workflow.runs.trace",
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

  it("accepts shared acyclic runtime values", () => {
    const schemas = runtimeSchemasFor("workflow.artifacts.inspect");
    const sharedSchema = {};
    const result = {
      id: "report",
      version: 1,
      title: "Report",
      kind: "workflow",
      description: null,
      outcomes: [],
      input_schema: sharedSchema,
      output_schema: sharedSchema,
      plan: {},
      required_capabilities: [],
      workflow_dependencies: {},
      created_from_catalog_version: null,
    };

    expect(accepts(schemas.success, result)).toBe(true);
  });

  it("rejects cyclic runtime values", () => {
    const schemas = runtimeSchemasFor("workflow.artifacts.inspect");
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;

    const result = {
      id: "report",
      version: 1,
      title: "Report",
      kind: "workflow",
      description: null,
      outcomes: [],
      input_schema: {},
      output_schema: {},
      plan: cyclic,
      required_capabilities: [],
      workflow_dependencies: {},
      created_from_catalog_version: null,
    };

    expect(accepts(schemas.success, result)).toBe(false);
  });

  it("accepts the maximum permitted container depth", () => {
    const schemas = runtimeSchemasFor("workflow.artifacts.inspect");
    let plan: unknown = "leaf";
    for (let depth = 0; depth < 63; depth += 1) plan = { nested: plan };

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
    ).toBe(true);
  });

  it("requires the canonical persisted interrupt contract", () => {
    const schemas = runtimeSchemasFor("workflow.runs.inspect");
    const baseRun = {
      run_id: "run_1",
      deployment_id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      status: "interrupted",
      resume_readiness: "ready",
      outcome: null,
      error: null,
      output: null,
      diagnostics: [],
      trace_count: 1,
      next_actions: {
        can_continue: true,
        can_save_now: null,
        recommended_next_tool: "wf.workflow.resume_run",
        reason: "run is interrupted",
        patch_examples: [],
        warnings: [],
      },
    };
    const completeInterrupt = {
      id: "interrupt_1",
      frame_id: "frame_1",
      node_id: "review_issues",
      kind: "issue_review",
      payload: {},
      resumable: true,
      route: null,
      outcomes: ["submitted", "cancelled"],
      request_schema: { type: "object" },
      resume_schema: { type: "object" },
      typed: true,
    };

    expect(accepts(schemas.success, { ...baseRun, interrupt: completeInterrupt })).toBe(
      true,
    );
    expect(
      accepts(schemas.success, {
        ...baseRun,
        interrupt: { kind: "issue_review", payload: {}, outcomes: [] },
      }),
    ).toBe(false);
    expect(
      accepts(schemas.success, {
        ...baseRun,
        run_id: null,
        status: "failed",
        resume_readiness: null,
        interrupt: null,
      }),
    ).toBe(true);
  });

  it("keeps canonical run input defaults optional", () => {
    const start = runtimeSchemasFor("workflow.runs.start");
    const resume = runtimeSchemasFor("workflow.runs.resume");
    const trace = runtimeSchemasFor("workflow.runs.trace");

    expect(accepts(start.payload, { deployment_id: "report.default" })).toBe(true);
    expect(accepts(resume.payload, { run_id: "run_1" })).toBe(true);
    expect(accepts(trace.payload, { run_id: "run_1", trace_range: {} })).toBe(true);
    expect(
      accepts(trace.payload, {
        run_id: "run_1",
        trace_range: { start: 0, limit: 101 },
      }),
    ).toBe(false);
  });

  it("requires the full run envelope and canonical trace frame identifiers", () => {
    const schemas = runtimeSchemasFor("workflow.runs.trace");
    const trace = [
      {
        frame_id: "frame_1",
        node_id: "review_issues",
        step_type: "interrupt",
        resolved_input: {},
        outcome: "submitted",
        next_node_id: "create_issues",
        output: {},
        state_changes: {},
      },
    ];
    const result = {
      run_id: "run_1",
      deployment_id: "report.default",
      artifact_id: "report",
      artifact_version: 1,
      status: "completed",
      resume_readiness: "not_applicable",
      interrupt: null,
      outcome: "completed",
      error: null,
      output: {},
      diagnostics: [],
      trace_count: 1,
      next_actions: {
        can_continue: false,
        can_save_now: null,
        recommended_next_tool: null,
        reason: "run completed",
        patch_examples: [],
        warnings: [],
      },
      trace,
      trace_start: 0,
      trace_limit: 50,
      trace_truncated: false,
    };

    expect(accepts(schemas.success, result)).toBe(true);
    expect(
      accepts(schemas.success, {
        run_id: "run_1",
        status: "completed",
        trace,
        trace_start: 0,
        trace_limit: 50,
        trace_truncated: false,
      }),
    ).toBe(false);
  });
});

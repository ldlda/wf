import { Schema } from "effect";

const NonNegativeIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(0, Number.MAX_SAFE_INTEGER),
);
const PositiveIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER),
);
const JsonObjectSchema = Schema.Record({
  key: Schema.String,
  value: Schema.Unknown,
});

const SourceSummarySchema = Schema.Struct({
  id: Schema.String,
  kind: Schema.String,
  enabled: Schema.Boolean,
  description: Schema.NullOr(Schema.String),
  tool_count: NonNegativeIntegerSchema,
  node_spec_count: NonNegativeIntegerSchema,
  reducer_count: NonNegativeIntegerSchema,
  prompt_count: NonNegativeIntegerSchema,
  resource_count: NonNegativeIntegerSchema,
});

const ArtifactNodeSchema = Schema.Struct({
  name: Schema.String,
  artifact_id: Schema.String,
  version: PositiveIntegerSchema,
  kind: Schema.String,
  display_name: Schema.String,
  description: Schema.NullOr(Schema.String),
  outcomes: Schema.Array(Schema.String),
  input_schema: JsonObjectSchema,
  output_schema: JsonObjectSchema,
  required_sources: Schema.Array(Schema.String),
  diagnostics: Schema.Array(Schema.Unknown),
});

const DeploymentNodeSchema = Schema.Struct({
  id: Schema.String,
  artifact_id: Schema.String,
  artifact_version: PositiveIntegerSchema,
  binding_count: NonNegativeIntegerSchema,
  drift_policy: Schema.String,
});

const DeploymentBindingSchema = Schema.Struct({
  logical_source: Schema.String,
  concrete_source: Schema.String,
});

const RunNodeSchema = Schema.Struct({
  run_id: Schema.String,
  deployment_id: Schema.String,
  artifact_id: Schema.String,
  artifact_version: PositiveIntegerSchema,
  status: Schema.String,
  resume_readiness: Schema.String,
  diagnostic_count: NonNegativeIntegerSchema,
  created_at: Schema.String,
  updated_at: Schema.String,
});

/** Frozen pre-migration schemas used only to detect generated-decoder drift. */
export const authoredCleanRpcSchemas = {
  "workflow.health": {
    payload: Schema.Struct({}),
    success: Schema.Struct({
      status: Schema.Literal("ok"),
      store_root: Schema.String,
    }),
  },
  "workflow.sources.list": {
    payload: Schema.Struct({
      cursor: Schema.optional(Schema.String),
      limit: Schema.optional(
        Schema.Number.pipe(Schema.int(), Schema.between(1, 100)),
      ),
    }),
    success: Schema.Struct({
      sources: Schema.Array(SourceSummarySchema),
      next_cursor: Schema.NullOr(Schema.String),
      total: NonNegativeIntegerSchema,
    }),
  },
  "workflow.artifacts.list": {
    payload: Schema.Struct({
      query: Schema.optional(Schema.String),
      kind: Schema.optional(Schema.Literal("workflow", "wrapper")),
      cursor: Schema.optional(Schema.String),
      limit: Schema.optional(PositiveIntegerSchema),
    }),
    success: Schema.Struct({
      nodes: Schema.Array(ArtifactNodeSchema),
      total: NonNegativeIntegerSchema,
      cursor: Schema.optional(Schema.NullOr(Schema.String)),
      next_cursor: Schema.NullOr(Schema.String),
      limit: Schema.optional(PositiveIntegerSchema),
    }),
  },
  "workflow.artifacts.inspect": {
    payload: Schema.Struct({
      artifact_id: Schema.String,
      version: PositiveIntegerSchema,
    }),
    success: Schema.Struct({
      id: Schema.String,
      version: PositiveIntegerSchema,
      title: Schema.String,
      kind: Schema.String,
      description: Schema.NullOr(Schema.String),
      outcomes: Schema.Array(Schema.String),
      input_schema: JsonObjectSchema,
      output_schema: JsonObjectSchema,
      plan: JsonObjectSchema,
      required_capabilities: Schema.Unknown,
      workflow_dependencies: Schema.Record({
        key: Schema.String,
        value: Schema.Number,
      }),
      created_from_catalog_version: Schema.NullOr(Schema.String),
    }),
  },
  "workflow.deployments.list": {
    payload: Schema.Struct({}),
    success: Schema.Struct({ deployments: Schema.Array(DeploymentNodeSchema) }),
  },
  "workflow.deployments.inspect": {
    payload: Schema.Struct({ deployment_id: Schema.String }),
    success: Schema.Struct({
      id: Schema.String,
      artifact_id: Schema.String,
      artifact_version: PositiveIntegerSchema,
      bindings: Schema.Array(DeploymentBindingSchema),
      drift_policy: Schema.String,
    }),
  },
  "workflow.deployments.validate": {
    payload: Schema.Struct({
      deployment_id: Schema.String,
      live_check: Schema.optional(Schema.Boolean),
    }),
    success: Schema.Struct({
      deployment_id: Schema.String,
      artifact_id: Schema.String,
      artifact_version: PositiveIntegerSchema,
      status: Schema.Literal("runnable", "unrunnable"),
      diagnostics: Schema.Array(Schema.Unknown),
      next_actions: Schema.Struct({
        can_continue: Schema.Boolean,
        can_save_now: Schema.NullOr(Schema.Boolean),
        recommended_next_tool: Schema.NullOr(Schema.String),
        reason: Schema.String,
        patch_examples: Schema.Array(Schema.Unknown),
        warnings: Schema.Array(Schema.String),
      }),
    }),
  },
  "workflow.runs.list": {
    payload: Schema.Struct({
      status: Schema.optional(
        Schema.Literal("completed", "failed", "interrupted"),
      ),
      cursor: Schema.optional(Schema.String),
      limit: Schema.optional(PositiveIntegerSchema),
    }),
    success: Schema.Struct({
      runs: Schema.Array(RunNodeSchema),
      total: NonNegativeIntegerSchema,
      cursor: Schema.NullOr(Schema.String),
      next_cursor: Schema.NullOr(Schema.String),
      limit: PositiveIntegerSchema,
    }),
  },
};

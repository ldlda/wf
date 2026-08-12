import { Schema } from "effect";

type JsonValue = string | number | boolean | null | JsonValue[] | { readonly [key: string]: JsonValue };

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
const PathSegmentSchema = Schema.String.pipe(Schema.minLength(1));
// This fixture intentionally mirrors the canonical recursive JSON literal contract.
const JsonValueStructureSchema: Schema.Schema<JsonValue, JsonValue, never> =
  Schema.suspend(
    (): Schema.Schema<JsonValue, JsonValue, never> =>
      Schema.Union(
        Schema.String,
        Schema.JsonNumber,
        Schema.Boolean,
        Schema.Null,
        Schema.Array(JsonValueStructureSchema),
        Schema.Record({ key: Schema.String, value: JsonValueStructureSchema }),
      ),
  );
const JsonValueSchema: Schema.Schema<JsonValue, unknown, never> =
  Schema.Unknown.pipe(
    Schema.filter(
      (value): value is JsonValue => {
        if (
          value === null ||
          typeof value === "boolean" ||
          typeof value === "string"
        ) {
          return true;
        }
        if (typeof value === "number") return Number.isFinite(value);
        if (typeof value !== "object") return false;
        if (Array.isArray(value)) return value.every((item) => item !== undefined);
        return Object.values(value).every((item) => item !== undefined);
      },
      { message: () => "value must be valid JSON" },
    ),
    Schema.transform(JsonValueStructureSchema, {
      strict: false,
      decode: (value) => value,
      encode: (value) => value,
    }),
  );

const WrapperHintsSchema = Schema.Struct({
  capability_name: Schema.String,
  confidence: Schema.Literal("high", "medium", "low"),
  declared_outcomes: Schema.Array(Schema.String),
  input_map: Schema.Record({ key: Schema.String, value: Schema.String }),
  input_schema: JsonObjectSchema,
  missing_decisions: Schema.Array(Schema.Unknown),
  notes: Schema.Array(Schema.String),
  outcome_candidates: Schema.Array(Schema.Unknown),
  outcome_policy: Schema.Literal(
    "preserve_declared",
    "manual_mapping_required",
  ),
  output_map: Schema.Record({ key: Schema.String, value: Schema.String }),
  output_schema: JsonObjectSchema,
  state_schema: JsonObjectSchema,
  suggested_wrapper_outcomes: Schema.Array(Schema.String),
});

const CapabilitySummarySchema = Schema.Union(
  Schema.Struct({
    kind: Schema.Literal("node_spec"),
    name: Schema.String,
    source_id: Schema.String,
    description: Schema.NullOr(Schema.String),
    outcomes: Schema.Array(Schema.String),
    is_async: Schema.Boolean,
    input_fields: Schema.Array(Schema.String),
    output_fields: Schema.Array(Schema.String),
  }),
  Schema.Struct({
    kind: Schema.Literal("wrapper_artifact"),
    name: Schema.String,
    source_id: Schema.String,
    description: Schema.NullOr(Schema.String),
    outcomes: Schema.Array(Schema.String),
    is_async: Schema.Boolean,
    input_fields: Schema.Array(Schema.String),
    output_fields: Schema.Array(Schema.String),
    artifact_id: Schema.String,
    version: PositiveIntegerSchema,
    title: Schema.String,
  }),
);

const CapabilityDetailSchema = Schema.Union(
  Schema.Struct({
    accepts_context: Schema.Boolean,
    description: Schema.NullOr(Schema.String),
    input_schema: JsonObjectSchema,
    is_async: Schema.Boolean,
    kind: Schema.Literal("node_spec"),
    name: Schema.String,
    outcomes: Schema.Array(Schema.String),
    output_schema: JsonObjectSchema,
    source_id: Schema.String,
    wrapper_hints: WrapperHintsSchema,
  }),
  Schema.Struct({
    artifact_id: Schema.String,
    description: Schema.NullOr(Schema.String),
    input_schema: JsonObjectSchema,
    is_async: Schema.Boolean,
    kind: Schema.Literal("wrapper_artifact"),
    name: Schema.String,
    outcomes: Schema.Array(Schema.String),
    output_schema: JsonObjectSchema,
    required_capabilities: Schema.Record({
      key: Schema.String,
      value: Schema.Unknown,
    }),
    source_id: Schema.String,
    title: Schema.String,
    version: PositiveIntegerSchema,
    wrapper_hints: WrapperHintsSchema,
  }),
);

const DraftDiagnosticSchema = Schema.Struct({
  code: Schema.String,
  details: Schema.optional(JsonObjectSchema),
  message: Schema.String,
  path: Schema.String,
  repair_hint: Schema.optional(Schema.NullOr(Schema.String)),
  step_id: Schema.optional(Schema.NullOr(Schema.String)),
});

const DraftWorkspaceSchema = Schema.Struct({
  diagnostics: Schema.Array(DraftDiagnosticSchema),
  draft: Schema.optional(JsonObjectSchema),
  revision: PositiveIntegerSchema,
  status: Schema.Literal("valid", "invalid", "conflict"),
  summary: Schema.Struct({
    name: Schema.Unknown,
    route_count: NonNegativeIntegerSchema,
    start: Schema.Unknown,
    step_count: NonNegativeIntegerSchema,
    steps: Schema.Array(Schema.String),
  }),
  title: Schema.NullOr(Schema.String),
  workspace_id: Schema.String,
});

// Effect's empty Struct does not traverse excess keys; the impossible optional
// field keeps the authored empty payload strict under onExcessProperty:error.
const EmptyPayloadSchema = Schema.Struct({
  __no_parameters: Schema.optional(Schema.Never),
});

export type AuthoredRpcFixture = {
  readonly payload: Schema.Schema.AnyNoContext;
  readonly success: Schema.Schema.AnyNoContext;
};

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

const TraceRangeSchema = Schema.Struct({
  start: NonNegativeIntegerSchema,
  limit: PositiveIntegerSchema,
});
const RunInterruptSchema = Schema.Struct({
  kind: Schema.String,
  payload: JsonObjectSchema,
  outcomes: Schema.Array(Schema.String),
  request_schema: Schema.optional(JsonObjectSchema),
  resume_schema: Schema.optional(JsonObjectSchema),
  typed: Schema.optional(Schema.Boolean),
});
const RunNextActionsSchema = Schema.Struct({
  can_continue: Schema.Boolean,
  can_save_now: Schema.NullOr(Schema.Boolean),
  recommended_next_tool: Schema.NullOr(Schema.String),
  reason: Schema.String,
  patch_examples: Schema.Array(Schema.Unknown),
  warnings: Schema.Array(Schema.String),
});
const RunResultSchema = Schema.Struct({
  run_id: Schema.String,
  deployment_id: Schema.String,
  artifact_id: Schema.String,
  artifact_version: PositiveIntegerSchema,
  status: Schema.String,
  resume_readiness: Schema.String,
  interrupt: Schema.NullOr(RunInterruptSchema),
  outcome: Schema.NullOr(Schema.String),
  error: Schema.NullOr(Schema.String),
  output: Schema.NullOr(JsonObjectSchema),
  diagnostics: Schema.Array(Schema.Unknown),
  trace_count: NonNegativeIntegerSchema,
  next_actions: RunNextActionsSchema,
});
const TraceFrameSchema = Schema.Struct({
  node_id: Schema.String,
  step_type: Schema.String,
  resolved_input: JsonObjectSchema,
  outcome: Schema.String,
  output: JsonObjectSchema,
  state_changes: JsonObjectSchema,
});

const StructuralPathPartsSchema = Schema.Array(PathSegmentSchema);
const StatePathPartsSchema = StructuralPathPartsSchema.pipe(
  Schema.filter((parts) => parts.length > 0),
);

const InputPathBindingSchema = Schema.Struct({
  path: Schema.Union(
    Schema.String,
    Schema.Struct({
      parts: StructuralPathPartsSchema,
      root: Schema.Literal("input", "state", "context"),
    }),
  ),
  target: Schema.Union(
    Schema.String,
    Schema.Struct({
      parts: StructuralPathPartsSchema,
      root: Schema.Literal("local"),
    }),
  ),
});

const InputValueBindingSchema = Schema.Struct({
  target: Schema.Union(
    Schema.String,
    Schema.Struct({
      parts: StructuralPathPartsSchema,
      root: Schema.Literal("local"),
    }),
  ),
  value: JsonValueSchema,
});

const InputBindingSchema = Schema.Union(
  InputPathBindingSchema,
  InputValueBindingSchema,
);

const OutputBindingSchema = Schema.Struct({
  source: Schema.Union(
    Schema.String,
    Schema.Struct({
      parts: StructuralPathPartsSchema,
      root: Schema.Literal("local"),
    }),
  ),
  target: Schema.Union(
    Schema.String,
    Schema.Struct({
      parts: StatePathPartsSchema,
      root: Schema.Literal("state"),
    }),
  ),
});

const CapabilityStepUpdateSchema = Schema.Struct({
  desc: Schema.optional(Schema.NullOr(Schema.String.pipe(Schema.minLength(1)))),
  input: Schema.optional(Schema.NullOr(Schema.Array(InputBindingSchema))),
  retry: Schema.optional(Schema.NullOr(NonNegativeIntegerSchema)),
  timeout_seconds: Schema.optional(Schema.NullOr(PositiveIntegerSchema)),
});

const CreateDraftWorkspaceFromCapabilityResultSchema = Schema.Struct({
  diagnostics: Schema.Array(DraftDiagnosticSchema),
  draft: Schema.optional(JsonObjectSchema),
  next_actions: RunNextActionsSchema,
  revision: PositiveIntegerSchema,
  status: Schema.Literal("valid", "invalid", "conflict"),
  summary: Schema.Struct({
    name: Schema.Unknown,
    route_count: NonNegativeIntegerSchema,
    start: Schema.Unknown,
    step_count: NonNegativeIntegerSchema,
    steps: Schema.Array(Schema.String),
  }),
  title: Schema.NullOr(Schema.String),
  workspace_id: Schema.String,
  wrapper_hints: WrapperHintsSchema,
});

/** Frozen pre-migration schemas used only to detect generated-decoder drift. */
export const authoredRpcSchemas = {
  "workflow.health": {
    payload: EmptyPayloadSchema,
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
  "workflow.capabilities.list": {
    payload: Schema.Struct({
      query: Schema.optional(Schema.NullOr(Schema.String)),
      source_id: Schema.optional(Schema.NullOr(Schema.String)),
      cursor: Schema.optional(Schema.NullOr(Schema.String)),
      limit: Schema.optional(
        Schema.Number.pipe(Schema.int(), Schema.between(1, 200)),
      ),
    }),
    success: Schema.Struct({
      capabilities: Schema.Array(CapabilitySummarySchema),
      next_cursor: Schema.NullOr(Schema.String),
      total: NonNegativeIntegerSchema,
    }),
  },
  "workflow.capabilities.inspect": {
    payload: Schema.Struct({
      qualified_name: Schema.String.pipe(Schema.minLength(1)),
    }),
    success: CapabilityDetailSchema,
  },
  "workflow.draft_workspaces.list": {
    payload: EmptyPayloadSchema,
    success: Schema.Struct({
      workspaces: Schema.Array(DraftWorkspaceSchema),
    }),
  },
  "workflow.draft_workspaces.get": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
      include_draft: Schema.optional(Schema.Boolean),
    }),
    success: DraftWorkspaceSchema,
  },
  "workflow.draft_workspaces.create_empty": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
      name: Schema.String.pipe(Schema.minLength(1)),
      title: Schema.optional(Schema.NullOr(Schema.String)),
      input_schema: Schema.optional(Schema.NullOr(JsonObjectSchema)),
      state_schema: Schema.optional(Schema.NullOr(JsonObjectSchema)),
      output_schema: Schema.optional(Schema.NullOr(JsonObjectSchema)),
      outcomes: Schema.optional(Schema.Array(Schema.String)),
    }),
    success: DraftWorkspaceSchema,
  },
  "workflow.draft_workspaces.create_from_capability": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
      capability_name: Schema.String.pipe(Schema.minLength(1)),
      name: Schema.optional(Schema.NullOr(Schema.String)),
      title: Schema.optional(Schema.NullOr(Schema.String)),
      input_schema: Schema.optional(Schema.NullOr(JsonObjectSchema)),
      state_schema: Schema.optional(Schema.NullOr(JsonObjectSchema)),
      output_schema: Schema.optional(Schema.NullOr(JsonObjectSchema)),
      input: Schema.optional(Schema.NullOr(Schema.Array(Schema.Unknown))),
      output: Schema.optional(Schema.NullOr(Schema.Array(Schema.Unknown))),
      input_map: Schema.optional(
        Schema.NullOr(Schema.Record({ key: Schema.String, value: Schema.String })),
      ),
      output_map: Schema.optional(
        Schema.NullOr(Schema.Record({ key: Schema.String, value: Schema.String })),
      ),
      error_message_source: Schema.optional(Schema.Unknown),
    }),
    success: CreateDraftWorkspaceFromCapabilityResultSchema,
  },
  "workflow.draft_workspaces.add_step_from_capability": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
      revision: PositiveIntegerSchema,
      step_id: Schema.String.pipe(Schema.minLength(1)),
      capability_name: Schema.String.pipe(Schema.minLength(1)),
      route_from_step: Schema.optional(Schema.NullOr(Schema.String)),
      route_from_outcome: Schema.optional(Schema.String),
      routes: Schema.optional(
        Schema.NullOr(Schema.Record({ key: Schema.String, value: Schema.String })),
      ),
      input_map: Schema.optional(
        Schema.NullOr(Schema.Record({ key: Schema.String, value: Schema.String })),
      ),
      input_bindings: Schema.optional(
        Schema.NullOr(Schema.Array(InputBindingSchema)),
      ),
      bind_outputs: Schema.optional(
        Schema.Record({ key: Schema.String, value: Schema.String }),
      ),
      desc: Schema.optional(Schema.NullOr(Schema.String.pipe(Schema.minLength(1)))),
      retry: Schema.optional(Schema.NullOr(NonNegativeIntegerSchema)),
      timeout_seconds: Schema.optional(Schema.NullOr(PositiveIntegerSchema)),
    }),
    success: DraftWorkspaceSchema,
  },
  "workflow.draft_workspaces.update_capability_step": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
      revision: PositiveIntegerSchema,
      step_id: Schema.String.pipe(Schema.minLength(1)),
      update: CapabilityStepUpdateSchema,
    }),
    success: DraftWorkspaceSchema,
  },
  "workflow.draft_workspaces.set_route": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
      revision: PositiveIntegerSchema,
      step_id: Schema.String.pipe(Schema.minLength(1)),
      outcome: Schema.String.pipe(Schema.minLength(1)),
      target: Schema.String.pipe(Schema.minLength(1)),
    }),
    success: DraftWorkspaceSchema,
  },
  "workflow.draft_workspaces.set_step_input_bindings": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
      revision: PositiveIntegerSchema,
      step_id: Schema.String.pipe(Schema.minLength(1)),
      bindings: Schema.Array(InputBindingSchema),
    }),
    success: DraftWorkspaceSchema,
  },
  "workflow.draft_workspaces.set_step_output_bindings": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
      revision: PositiveIntegerSchema,
      step_id: Schema.String.pipe(Schema.minLength(1)),
      bindings: Schema.Array(OutputBindingSchema),
    }),
    success: DraftWorkspaceSchema,
  },
  "workflow.draft_workspaces.validate": {
    payload: Schema.Struct({
      workspace_id: Schema.String.pipe(Schema.minLength(1)),
    }),
    success: DraftWorkspaceSchema,
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
    payload: EmptyPayloadSchema,
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
  "workflow.runs.inspect": {
    payload: Schema.Struct({ run_id: Schema.String }),
    success: RunResultSchema,
  },
  "workflow.runs.start": {
    payload: Schema.Struct({
      deployment_id: Schema.String,
      workflow_input: JsonObjectSchema,
      trace_range: Schema.optional(Schema.NullOr(TraceRangeSchema)),
    }),
    success: RunResultSchema,
  },
  "workflow.runs.resume": {
    payload: Schema.Struct({
      run_id: Schema.String,
      resume_payload: JsonObjectSchema,
      resume_outcome: Schema.optional(Schema.String),
      trace_range: Schema.optional(Schema.NullOr(TraceRangeSchema)),
    }),
    success: RunResultSchema,
  },
  "workflow.runs.trace": {
    payload: Schema.Struct({
      run_id: Schema.String,
      trace_range: TraceRangeSchema,
    }),
    success: Schema.Struct({
      run_id: Schema.String,
      status: Schema.String,
      trace: Schema.Array(TraceFrameSchema),
      trace_start: NonNegativeIntegerSchema,
      trace_limit: PositiveIntegerSchema,
      trace_truncated: Schema.Boolean,
    }),
  },
} satisfies Readonly<Record<string, AuthoredRpcFixture>>;

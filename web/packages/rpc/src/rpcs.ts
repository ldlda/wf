import { Rpc, RpcGroup } from "@effect/rpc";
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

export const ArtifactRefSchema = Schema.Struct({
  artifact_id: Schema.String,
  version: PositiveIntegerSchema,
});

export const TraceRangeSchema = Schema.Struct({
  start: NonNegativeIntegerSchema,
  limit: PositiveIntegerSchema,
});

export const SourceSummarySchema = Schema.Struct({
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

export const WorkflowHealthPayloadSchema = Schema.Struct({});
export const WorkflowHealthResultSchema = Schema.Struct({
  status: Schema.Literal("ok"),
  store_root: Schema.String,
});

export const WorkflowHealth = Rpc.make("workflow.health", {
  payload: WorkflowHealthPayloadSchema,
  success: WorkflowHealthResultSchema,
  error: Schema.Never,
});

export const WorkflowSourcesListPayloadSchema = Schema.Struct({
  cursor: Schema.optional(Schema.String),
  limit: Schema.optional(
    Schema.Number.pipe(Schema.int(), Schema.between(1, 100)),
  ),
});
export const WorkflowSourcesListResultSchema = Schema.Struct({
  sources: Schema.Array(SourceSummarySchema),
  next_cursor: Schema.NullOr(Schema.String),
  total: NonNegativeIntegerSchema,
});

export const WorkflowSourcesList = Rpc.make("workflow.sources.list", {
  payload: WorkflowSourcesListPayloadSchema,
  success: WorkflowSourcesListResultSchema,
  error: Schema.Never,
});

// Artifacts
export const WorkflowArtifactsListPayloadSchema = Schema.Struct({
  query: Schema.optional(Schema.String),
  kind: Schema.optional(Schema.Literal("workflow", "wrapper")),
  cursor: Schema.optional(Schema.String),
  limit: Schema.optional(PositiveIntegerSchema),
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

export const WorkflowArtifactsListResultSchema = Schema.Struct({
  nodes: Schema.Array(ArtifactNodeSchema),
  total: NonNegativeIntegerSchema,
  cursor: Schema.optional(Schema.NullOr(Schema.String)),
  next_cursor: Schema.NullOr(Schema.String),
  limit: Schema.optional(PositiveIntegerSchema),
});

export const WorkflowArtifactsList = Rpc.make("workflow.artifacts.list", {
  payload: WorkflowArtifactsListPayloadSchema,
  success: WorkflowArtifactsListResultSchema,
  error: Schema.Never,
});

export const WorkflowArtifactsInspectPayloadSchema = Schema.Struct({
  artifact_id: Schema.String,
  version: PositiveIntegerSchema,
});

export const WorkflowArtifactsInspectResultSchema = Schema.Struct({
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
  workflow_dependencies: Schema.Record({ key: Schema.String, value: Schema.Number }),
  created_from_catalog_version: Schema.NullOr(Schema.String),
});

export const WorkflowArtifactsInspect = Rpc.make("workflow.artifacts.inspect", {
  payload: WorkflowArtifactsInspectPayloadSchema,
  success: WorkflowArtifactsInspectResultSchema,
  error: Schema.Never,
});

// Deployments
export const WorkflowDeploymentsListPayloadSchema = Schema.Struct({});

const DeploymentNodeSchema = Schema.Struct({
  id: Schema.String,
  artifact_id: Schema.String,
  artifact_version: PositiveIntegerSchema,
  binding_count: NonNegativeIntegerSchema,
  drift_policy: Schema.String,
});

export const WorkflowDeploymentsListResultSchema = Schema.Struct({
  deployments: Schema.Array(DeploymentNodeSchema),
});

export const WorkflowDeploymentsList = Rpc.make("workflow.deployments.list", {
  payload: WorkflowDeploymentsListPayloadSchema,
  success: WorkflowDeploymentsListResultSchema,
  error: Schema.Never,
});

export const WorkflowDeploymentsInspectPayloadSchema = Schema.Struct({
  deployment_id: Schema.String,
});

const DeploymentBindingSchema = Schema.Struct({
  logical_source: Schema.String,
  concrete_source: Schema.String,
});

export const WorkflowDeploymentsInspectResultSchema = Schema.Struct({
  id: Schema.String,
  artifact_id: Schema.String,
  artifact_version: PositiveIntegerSchema,
  bindings: Schema.Array(DeploymentBindingSchema),
  drift_policy: Schema.String,
});

export const WorkflowDeploymentsInspect = Rpc.make("workflow.deployments.inspect", {
  payload: WorkflowDeploymentsInspectPayloadSchema,
  success: WorkflowDeploymentsInspectResultSchema,
  error: Schema.Never,
});

export const WorkflowDeploymentsValidatePayloadSchema = Schema.Struct({
  deployment_id: Schema.String,
  live_check: Schema.optional(Schema.Boolean),
});

export const WorkflowDeploymentsValidateResultSchema = Schema.Struct({
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
});

export const WorkflowDeploymentsValidate = Rpc.make("workflow.deployments.validate", {
  payload: WorkflowDeploymentsValidatePayloadSchema,
  success: WorkflowDeploymentsValidateResultSchema,
  error: Schema.Never,
});

// Runs
export const WorkflowRunsListPayloadSchema = Schema.Struct({
  status: Schema.optional(Schema.Literal("completed", "failed", "interrupted")),
  cursor: Schema.optional(Schema.String),
  limit: Schema.optional(PositiveIntegerSchema),
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

export const WorkflowRunsListResultSchema = Schema.Struct({
  runs: Schema.Array(RunNodeSchema),
  total: NonNegativeIntegerSchema,
  cursor: Schema.NullOr(Schema.String),
  next_cursor: Schema.NullOr(Schema.String),
  limit: PositiveIntegerSchema,
});

export const WorkflowRunsList = Rpc.make("workflow.runs.list", {
  payload: WorkflowRunsListPayloadSchema,
  success: WorkflowRunsListResultSchema,
  error: Schema.Never,
});

export const WorkflowRunsInspectPayloadSchema = Schema.Struct({
  run_id: Schema.String,
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

export const WorkflowRunsInspectResultSchema = Schema.Struct({
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

export const WorkflowRunsInspect = Rpc.make("workflow.runs.inspect", {
  payload: WorkflowRunsInspectPayloadSchema,
  success: WorkflowRunsInspectResultSchema,
  error: Schema.Never,
});

export const WorkflowRunsStartPayloadSchema = Schema.Struct({
  deployment_id: Schema.String,
  workflow_input: JsonObjectSchema,
  trace_range: Schema.optional(Schema.NullOr(TraceRangeSchema)),
});

export const WorkflowRunsResumePayloadSchema = Schema.Struct({
  run_id: Schema.String,
  resume_payload: JsonObjectSchema,
  resume_outcome: Schema.optional(Schema.String),
  trace_range: Schema.optional(Schema.NullOr(TraceRangeSchema)),
});

export const WorkflowRunsStart = Rpc.make("workflow.runs.start", {
  payload: WorkflowRunsStartPayloadSchema,
  success: WorkflowRunsInspectResultSchema,
  error: Schema.Never,
});

export const WorkflowRunsResume = Rpc.make("workflow.runs.resume", {
  payload: WorkflowRunsResumePayloadSchema,
  success: WorkflowRunsInspectResultSchema,
  error: Schema.Never,
});

export const WorkflowRunsTracePayloadSchema = Schema.Struct({
  run_id: Schema.String,
  trace_range: TraceRangeSchema,
});

const TraceFrameSchema = Schema.Struct({
  node_id: Schema.String,
  step_type: Schema.String,
  resolved_input: JsonObjectSchema,
  outcome: Schema.String,
  output: JsonObjectSchema,
  state_changes: JsonObjectSchema,
});

export const WorkflowRunsTraceResultSchema = Schema.Struct({
  run_id: Schema.String,
  status: Schema.String,
  trace: Schema.Array(TraceFrameSchema),
  trace_start: NonNegativeIntegerSchema,
  trace_limit: PositiveIntegerSchema,
  trace_truncated: Schema.Boolean,
});

export const WorkflowRunsTrace = Rpc.make("workflow.runs.trace", {
  payload: WorkflowRunsTracePayloadSchema,
  success: WorkflowRunsTraceResultSchema,
  error: Schema.Never,
});

export const WorkflowRpcs = RpcGroup.make(
  WorkflowHealth,
  WorkflowSourcesList,
  WorkflowArtifactsList,
  WorkflowArtifactsInspect,
  WorkflowDeploymentsList,
  WorkflowDeploymentsInspect,
  WorkflowDeploymentsValidate,
  WorkflowRunsList,
  WorkflowRunsInspect,
  WorkflowRunsStart,
  WorkflowRunsResume,
  WorkflowRunsTrace,
);

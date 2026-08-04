import { Rpc, RpcGroup } from "@effect/rpc";
import { Schema } from "effect";
import { runtimeSchemasFor } from "./json-schema/runtime-schema.js";

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

const healthSchemas = runtimeSchemasFor("workflow.health");
export const WorkflowHealthPayloadSchema = healthSchemas.payload;
export const WorkflowHealthResultSchema = healthSchemas.success;

export const WorkflowHealth = Rpc.make("workflow.health", {
  payload: WorkflowHealthPayloadSchema,
  success: WorkflowHealthResultSchema,
  error: Schema.Never,
});

const sourceListSchemas = runtimeSchemasFor("workflow.sources.list");
export const WorkflowSourcesListPayloadSchema = sourceListSchemas.payload;
export const WorkflowSourcesListResultSchema = sourceListSchemas.success;

export const WorkflowSourcesList = Rpc.make("workflow.sources.list", {
  payload: WorkflowSourcesListPayloadSchema,
  success: WorkflowSourcesListResultSchema,
  error: Schema.Never,
});

// Artifacts
const artifactListSchemas = runtimeSchemasFor("workflow.artifacts.list");
export const WorkflowArtifactsListPayloadSchema = artifactListSchemas.payload;
export const WorkflowArtifactsListResultSchema = artifactListSchemas.success;

export const WorkflowArtifactsList = Rpc.make("workflow.artifacts.list", {
  payload: WorkflowArtifactsListPayloadSchema,
  success: WorkflowArtifactsListResultSchema,
  error: Schema.Never,
});

const artifactInspectSchemas = runtimeSchemasFor("workflow.artifacts.inspect");
export const WorkflowArtifactsInspectPayloadSchema =
  artifactInspectSchemas.payload;
export const WorkflowArtifactsInspectResultSchema =
  artifactInspectSchemas.success;

export const WorkflowArtifactsInspect = Rpc.make("workflow.artifacts.inspect", {
  payload: WorkflowArtifactsInspectPayloadSchema,
  success: WorkflowArtifactsInspectResultSchema,
  error: Schema.Never,
});

// Deployments
const deploymentListSchemas = runtimeSchemasFor("workflow.deployments.list");
export const WorkflowDeploymentsListPayloadSchema =
  deploymentListSchemas.payload;
export const WorkflowDeploymentsListResultSchema = deploymentListSchemas.success;

export const WorkflowDeploymentsList = Rpc.make("workflow.deployments.list", {
  payload: WorkflowDeploymentsListPayloadSchema,
  success: WorkflowDeploymentsListResultSchema,
  error: Schema.Never,
});

const deploymentInspectSchemas = runtimeSchemasFor(
  "workflow.deployments.inspect",
);
export const WorkflowDeploymentsInspectPayloadSchema =
  deploymentInspectSchemas.payload;
export const WorkflowDeploymentsInspectResultSchema =
  deploymentInspectSchemas.success;

export const WorkflowDeploymentsInspect = Rpc.make("workflow.deployments.inspect", {
  payload: WorkflowDeploymentsInspectPayloadSchema,
  success: WorkflowDeploymentsInspectResultSchema,
  error: Schema.Never,
});

const deploymentValidateSchemas = runtimeSchemasFor(
  "workflow.deployments.validate",
);
export const WorkflowDeploymentsValidatePayloadSchema =
  deploymentValidateSchemas.payload;
export const WorkflowDeploymentsValidateResultSchema =
  deploymentValidateSchemas.success;

export const WorkflowDeploymentsValidate = Rpc.make("workflow.deployments.validate", {
  payload: WorkflowDeploymentsValidatePayloadSchema,
  success: WorkflowDeploymentsValidateResultSchema,
  error: Schema.Never,
});

// Runs
const runListSchemas = runtimeSchemasFor("workflow.runs.list");
export const WorkflowRunsListPayloadSchema = runListSchemas.payload;
export const WorkflowRunsListResultSchema = runListSchemas.success;

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

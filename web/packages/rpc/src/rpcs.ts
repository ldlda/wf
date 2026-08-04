import { Rpc, RpcGroup } from "@effect/rpc";
import { Schema } from "effect";
import { runtimeSchemasFor } from "./json-schema/runtime-schema.js";

const PositiveIntegerSchema = Schema.Number.pipe(
  Schema.int(),
  Schema.between(1, Number.MAX_SAFE_INTEGER),
);

export const ArtifactRefSchema = Schema.Struct({
  artifact_id: Schema.String,
  version: PositiveIntegerSchema,
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

const runInspectSchemas = runtimeSchemasFor("workflow.runs.inspect");
export const WorkflowRunsInspectPayloadSchema = runInspectSchemas.payload;
export const WorkflowRunsInspectResultSchema = runInspectSchemas.success;

export const WorkflowRunsInspect = Rpc.make("workflow.runs.inspect", {
  payload: WorkflowRunsInspectPayloadSchema,
  success: WorkflowRunsInspectResultSchema,
  error: Schema.Never,
});

const runStartSchemas = runtimeSchemasFor("workflow.runs.start");
export const WorkflowRunsStartPayloadSchema = runStartSchemas.payload;

const runResumeSchemas = runtimeSchemasFor("workflow.runs.resume");
export const WorkflowRunsResumePayloadSchema = runResumeSchemas.payload;

export const WorkflowRunsStart = Rpc.make("workflow.runs.start", {
  payload: WorkflowRunsStartPayloadSchema,
  success: runStartSchemas.success,
  error: Schema.Never,
});

export const WorkflowRunsResume = Rpc.make("workflow.runs.resume", {
  payload: WorkflowRunsResumePayloadSchema,
  success: runResumeSchemas.success,
  error: Schema.Never,
});

const runTraceSchemas = runtimeSchemasFor("workflow.runs.trace");
export const WorkflowRunsTracePayloadSchema = runTraceSchemas.payload;
export const WorkflowRunsTraceResultSchema = runTraceSchemas.success;

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

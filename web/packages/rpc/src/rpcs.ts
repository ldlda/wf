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

const capabilityListSchemas = runtimeSchemasFor("workflow.capabilities.list");
export const WorkflowCapabilitiesListPayloadSchema =
  capabilityListSchemas.payload;
export const WorkflowCapabilitiesListResultSchema =
  capabilityListSchemas.success;

export const WorkflowCapabilitiesList = Rpc.make("workflow.capabilities.list", {
  payload: WorkflowCapabilitiesListPayloadSchema,
  success: WorkflowCapabilitiesListResultSchema,
  error: Schema.Never,
});

const capabilityInspectSchemas = runtimeSchemasFor(
  "workflow.capabilities.inspect",
);
export const WorkflowCapabilitiesInspectPayloadSchema =
  capabilityInspectSchemas.payload;
export const WorkflowCapabilitiesInspectResultSchema =
  capabilityInspectSchemas.success;

export const WorkflowCapabilitiesInspect = Rpc.make(
  "workflow.capabilities.inspect",
  {
    payload: WorkflowCapabilitiesInspectPayloadSchema,
    success: WorkflowCapabilitiesInspectResultSchema,
    error: Schema.Never,
  },
);

const draftWorkspacesListSchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.list",
);
export const WorkflowDraftWorkspacesListPayloadSchema =
  draftWorkspacesListSchemas.payload;
export const WorkflowDraftWorkspacesListResultSchema =
  draftWorkspacesListSchemas.success;

export const WorkflowDraftWorkspacesList = Rpc.make(
  "workflow.draft_workspaces.list",
  {
    payload: WorkflowDraftWorkspacesListPayloadSchema,
    success: WorkflowDraftWorkspacesListResultSchema,
    error: Schema.Never,
  },
);

const draftWorkspacesGetSchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.get",
);
export const WorkflowDraftWorkspacesGetPayloadSchema =
  draftWorkspacesGetSchemas.payload;
export const WorkflowDraftWorkspacesGetResultSchema =
  draftWorkspacesGetSchemas.success;

export const WorkflowDraftWorkspacesGet = Rpc.make(
  "workflow.draft_workspaces.get",
  {
    payload: WorkflowDraftWorkspacesGetPayloadSchema,
    success: WorkflowDraftWorkspacesGetResultSchema,
    error: Schema.Never,
  },
);

// Artifacts
const artifactListSchemas = runtimeSchemasFor("workflow.artifacts.list");
export const WorkflowArtifactsListPayloadSchema = artifactListSchemas.payload;
export const WorkflowArtifactsListResultSchema = artifactListSchemas.success;

export const WorkflowArtifactsList = Rpc.make("workflow.artifacts.list", {
  payload: WorkflowArtifactsListPayloadSchema,
  success: WorkflowArtifactsListResultSchema,
  error: Schema.Never,
});

const draftWorkspacesCreateEmptySchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.create_empty",
);
export const WorkflowDraftWorkspacesCreateEmptyPayloadSchema =
  draftWorkspacesCreateEmptySchemas.payload;
export const WorkflowDraftWorkspacesCreateEmptyResultSchema =
  draftWorkspacesCreateEmptySchemas.success;

export const WorkflowDraftWorkspacesCreateEmpty = Rpc.make(
  "workflow.draft_workspaces.create_empty",
  {
    payload: WorkflowDraftWorkspacesCreateEmptyPayloadSchema,
    success: WorkflowDraftWorkspacesCreateEmptyResultSchema,
    error: Schema.Never,
  },
);

const draftWorkspacesCreateFromCapabilitySchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.create_from_capability",
);
export const WorkflowDraftWorkspacesCreateFromCapabilityPayloadSchema =
  draftWorkspacesCreateFromCapabilitySchemas.payload;
export const WorkflowDraftWorkspacesCreateFromCapabilityResultSchema =
  draftWorkspacesCreateFromCapabilitySchemas.success;

export const WorkflowDraftWorkspacesCreateFromCapability = Rpc.make(
  "workflow.draft_workspaces.create_from_capability",
  {
    payload: WorkflowDraftWorkspacesCreateFromCapabilityPayloadSchema,
    success: WorkflowDraftWorkspacesCreateFromCapabilityResultSchema,
    error: Schema.Never,
  },
);

const draftWorkspacesAddStepFromCapabilitySchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.add_step_from_capability",
);
export const WorkflowDraftWorkspacesAddStepFromCapabilityPayloadSchema =
  draftWorkspacesAddStepFromCapabilitySchemas.payload;
export const WorkflowDraftWorkspacesAddStepFromCapabilityResultSchema =
  draftWorkspacesAddStepFromCapabilitySchemas.success;

export const WorkflowDraftWorkspacesAddStepFromCapability = Rpc.make(
  "workflow.draft_workspaces.add_step_from_capability",
  {
    payload: WorkflowDraftWorkspacesAddStepFromCapabilityPayloadSchema,
    success: WorkflowDraftWorkspacesAddStepFromCapabilityResultSchema,
    error: Schema.Never,
  },
);

const draftWorkspacesUpdateCapabilityStepSchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.update_capability_step",
);
export const WorkflowDraftWorkspacesUpdateCapabilityStepPayloadSchema =
  draftWorkspacesUpdateCapabilityStepSchemas.payload;
export const WorkflowDraftWorkspacesUpdateCapabilityStepResultSchema =
  draftWorkspacesUpdateCapabilityStepSchemas.success;

export const WorkflowDraftWorkspacesUpdateCapabilityStep = Rpc.make(
  "workflow.draft_workspaces.update_capability_step",
  {
    payload: WorkflowDraftWorkspacesUpdateCapabilityStepPayloadSchema,
    success: WorkflowDraftWorkspacesUpdateCapabilityStepResultSchema,
    error: Schema.Never,
  },
);

const draftWorkspacesSetRouteSchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.set_route",
);
export const WorkflowDraftWorkspacesSetRoutePayloadSchema =
  draftWorkspacesSetRouteSchemas.payload;
export const WorkflowDraftWorkspacesSetRouteResultSchema =
  draftWorkspacesSetRouteSchemas.success;

export const WorkflowDraftWorkspacesSetRoute = Rpc.make(
  "workflow.draft_workspaces.set_route",
  {
    payload: WorkflowDraftWorkspacesSetRoutePayloadSchema,
    success: WorkflowDraftWorkspacesSetRouteResultSchema,
    error: Schema.Never,
  },
);

const setStepInputBindingsSchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.set_step_input_bindings",
);
export const WorkflowDraftWorkspacesSetStepInputBindingsPayloadSchema =
  setStepInputBindingsSchemas.payload;
export const WorkflowDraftWorkspacesSetStepInputBindingsResultSchema =
  setStepInputBindingsSchemas.success;

export const WorkflowDraftWorkspacesSetStepInputBindings = Rpc.make(
  "workflow.draft_workspaces.set_step_input_bindings",
  {
    payload: WorkflowDraftWorkspacesSetStepInputBindingsPayloadSchema,
    success: WorkflowDraftWorkspacesSetStepInputBindingsResultSchema,
    error: Schema.Never,
  },
);

const setStepOutputBindingsSchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.set_step_output_bindings",
);
export const WorkflowDraftWorkspacesSetStepOutputBindingsPayloadSchema =
  setStepOutputBindingsSchemas.payload;
export const WorkflowDraftWorkspacesSetStepOutputBindingsResultSchema =
  setStepOutputBindingsSchemas.success;

export const WorkflowDraftWorkspacesSetStepOutputBindings = Rpc.make(
  "workflow.draft_workspaces.set_step_output_bindings",
  {
    payload: WorkflowDraftWorkspacesSetStepOutputBindingsPayloadSchema,
    success: WorkflowDraftWorkspacesSetStepOutputBindingsResultSchema,
    error: Schema.Never,
  },
);

const draftWorkspacesValidateSchemas = runtimeSchemasFor(
  "workflow.draft_workspaces.validate",
);
export const WorkflowDraftWorkspacesValidatePayloadSchema =
  draftWorkspacesValidateSchemas.payload;
export const WorkflowDraftWorkspacesValidateResultSchema =
  draftWorkspacesValidateSchemas.success;

export const WorkflowDraftWorkspacesValidate = Rpc.make(
  "workflow.draft_workspaces.validate",
  {
    payload: WorkflowDraftWorkspacesValidatePayloadSchema,
    success: WorkflowDraftWorkspacesValidateResultSchema,
    error: Schema.Never,
  },
);

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
export const WorkflowRunsStartResultSchema = runStartSchemas.success;

const runResumeSchemas = runtimeSchemasFor("workflow.runs.resume");
export const WorkflowRunsResumePayloadSchema = runResumeSchemas.payload;
export const WorkflowRunsResumeResultSchema = runResumeSchemas.success;

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
  WorkflowCapabilitiesList,
  WorkflowCapabilitiesInspect,
  WorkflowDraftWorkspacesList,
  WorkflowDraftWorkspacesGet,
  WorkflowDraftWorkspacesCreateEmpty,
  WorkflowDraftWorkspacesCreateFromCapability,
  WorkflowDraftWorkspacesAddStepFromCapability,
  WorkflowDraftWorkspacesUpdateCapabilityStep,
  WorkflowDraftWorkspacesSetRoute,
  WorkflowDraftWorkspacesSetStepInputBindings,
  WorkflowDraftWorkspacesSetStepOutputBindings,
  WorkflowDraftWorkspacesValidate,
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

export {
  InvalidTargetError,
  UnknownOperationError,
  UpstreamConnectionError,
  UpstreamTimeoutError,
  UpstreamResponseTooLargeError,
  RpcProtocolError,
  RpcRemoteError,
  RpcDecodeError,
} from "./errors.js";

export { normalizeLoopbackTarget } from "./target-policy.js";

export {
  hasBoundedInputExpressionNodeBudget,
  MAX_INPUT_EXPRESSION_DEPTH,
  MAX_INPUT_EXPRESSION_NODES,
} from "./json-schema/input-expression-limits.js";

// Compile-time wire inventory only; supported operations and browser policy stay authored.
export * from "./generated/workflow-contract.js";

export {
  WorkflowHealth,
  WorkflowSourcesList,
  WorkflowCapabilitiesList,
  WorkflowCapabilitiesInspect,
  WorkflowCapabilitiesCall,
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
  WorkflowCapabilitiesListPayloadSchema,
  WorkflowCapabilitiesListResultSchema,
  WorkflowCapabilitiesInspectPayloadSchema,
  WorkflowCapabilitiesInspectResultSchema,
  WorkflowCapabilitiesCallPayloadSchema,
  WorkflowCapabilitiesCallResultSchema,
  WorkflowDraftWorkspacesListPayloadSchema,
  WorkflowDraftWorkspacesListResultSchema,
  WorkflowDraftWorkspacesGetPayloadSchema,
  WorkflowDraftWorkspacesGetResultSchema,
  WorkflowDraftWorkspacesCreateEmptyPayloadSchema,
  WorkflowDraftWorkspacesCreateEmptyResultSchema,
  WorkflowDraftWorkspacesCreateFromCapabilityPayloadSchema,
  WorkflowDraftWorkspacesCreateFromCapabilityResultSchema,
  WorkflowDraftWorkspacesAddStepFromCapabilityPayloadSchema,
  WorkflowDraftWorkspacesAddStepFromCapabilityResultSchema,
  WorkflowDraftWorkspacesUpdateCapabilityStepPayloadSchema,
  WorkflowDraftWorkspacesUpdateCapabilityStepResultSchema,
  WorkflowDraftWorkspacesSetRoutePayloadSchema,
  WorkflowDraftWorkspacesSetRouteResultSchema,
  WorkflowDraftWorkspacesSetStepInputBindingsPayloadSchema,
  WorkflowDraftWorkspacesSetStepInputBindingsResultSchema,
  WorkflowDraftWorkspacesSetStepOutputBindingsPayloadSchema,
  WorkflowDraftWorkspacesSetStepOutputBindingsResultSchema,
  WorkflowDraftWorkspacesValidatePayloadSchema,
  WorkflowDraftWorkspacesValidateResultSchema,
  WorkflowRpcs,
  ArtifactRefSchema,
} from "./rpcs.js";

export { WorkflowRpc, makeWorkflowRpcLayer } from "./service.js";
export type { OperationExchange, WorkflowRpcError } from "./service.js";

export {
  getOperationMeta,
  isOperationName,
  listOperations,
  workflowRpcOperationNames,
} from "./method-registry.js";
export type {
  OperationName,
  OperationMeta,
  WorkflowHealthInterpreted,
  WorkflowSourcesListInterpreted,
  CapabilitySummaryInterpreted,
  CapabilityCallInterpreted,
  DraftWorkspaceInterpreted,
} from "./method-registry.js";

export {
  EvidenceRef,
  makeEvidenceLayer,
  withEvidenceCapture,
} from "./evidence.js";
export type { EvidenceRecord } from "./evidence.js";

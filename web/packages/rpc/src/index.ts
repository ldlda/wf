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

// Compile-time wire inventory only; supported operations and browser policy stay authored.
export * from "./generated/workflow-contract.js";

export {
  WorkflowHealth,
  WorkflowSourcesList,
  WorkflowCapabilitiesList,
  WorkflowCapabilitiesInspect,
  WorkflowDraftWorkspacesList,
  WorkflowDraftWorkspacesGet,
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
  WorkflowDraftWorkspacesListPayloadSchema,
  WorkflowDraftWorkspacesListResultSchema,
  WorkflowDraftWorkspacesGetPayloadSchema,
  WorkflowDraftWorkspacesGetResultSchema,
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
  DraftWorkspaceInterpreted,
} from "./method-registry.js";

export {
  EvidenceRef,
  makeEvidenceLayer,
  withEvidenceCapture,
} from "./evidence.js";
export type { EvidenceRecord } from "./evidence.js";

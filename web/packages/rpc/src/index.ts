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

export { WorkflowHealth, WorkflowSourcesList, WorkflowRpcs } from "./rpcs.js";

export { WorkflowRpc, makeWorkflowRpcLayer } from "./service.js";
export type { OperationExchange, WorkflowRpcError, OperationName } from "./service.js";

export {
  getOperationMeta,
  listOperations,
} from "./method-registry.js";
export type {
  OperationMeta,
  WorkflowHealthInterpreted,
  WorkflowSourcesListInterpreted,
} from "./method-registry.js";

export {
  EvidenceRef,
  makeEvidenceLayer,
  withEvidenceCapture,
} from "./evidence.js";
export type { EvidenceRecord } from "./evidence.js";

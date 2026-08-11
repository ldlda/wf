import type { ConnectionSuccess } from "../connection/contracts.js";
import { retainEvidence } from "../workspace/domain/evidence-policy.js";

export type ConnectionPhase =
  | "not_configured"
  | "connecting"
  | "connected"
  | "invalid_target"
  | "console_backend_unreachable"
  | "unreachable"
  | "rpc_error"
  | "malformed_response";

export type EvidenceRecord = {
  readonly id: string;
  readonly target: string;
  readonly operation: string;
  readonly label: string;
  readonly equivalentCli: string;
  readonly request: unknown;
  readonly response: unknown;
  readonly durationMs: number;
};

export type ConnectionState = {
  readonly phase: ConnectionPhase;
  readonly draftTarget: string;
  readonly connectedTarget: string | null;
  readonly serverStatus: string | null;
  readonly storeRoot: string | null;
  readonly durationMs: number | null;
  readonly message: string | null;
  readonly evidence: ReadonlyArray<EvidenceRecord>;
};

export const STORAGE_KEY = "lda.workflowConsole.target";

const safeSessionStorage = (): Storage | null => {
  try {
    return typeof sessionStorage !== "undefined" ? sessionStorage : null;
  } catch {
    return null;
  }
};

const getDefaultTarget = (): string => {
  const ss = safeSessionStorage();
  return ss?.getItem(STORAGE_KEY) ?? "http://127.0.0.1:8765/rpc";
};

export const initialState = (): ConnectionState => ({
  phase: "not_configured",
  draftTarget: getDefaultTarget(),
  connectedTarget: null,
  serverStatus: null,
  storeRoot: null,
  durationMs: null,
  message: null,
  evidence: [],
});

export type ConnectionAction =
  | { readonly type: "submit"; readonly target: string }
  | { readonly type: "success"; readonly data: ConnectionSuccess }
  | { readonly type: "failure"; readonly code: string; readonly message: string }
  | { readonly type: "draft_changed"; readonly value: string }
  | { readonly type: "evidence_recorded"; readonly record: EvidenceRecord };

export const connectionReducer = (
  state: ConnectionState,
  action: ConnectionAction,
): ConnectionState => {
  switch (action.type) {
    case "submit":
      return {
        ...state,
        phase: "connecting",
        draftTarget: action.target,
        message: null,
      };

    case "success": {
      const normalizedTarget = action.data.connection.target;
      const ss = safeSessionStorage();
      ss?.setItem(STORAGE_KEY, normalizedTarget);
      return {
        ...state,
        phase: "connected",
        draftTarget: normalizedTarget,
        connectedTarget: normalizedTarget,
        serverStatus: action.data.connection.serverStatus,
        storeRoot: action.data.connection.storeRoot,
        durationMs: action.data.connection.durationMs,
        message: null,
      };
    }

    case "failure": {
      const phase: ConnectionPhase = mapCodeToPhase(action.code);
      return {
        ...state,
        phase,
        message: action.message,
      };
    }

    case "draft_changed":
      return {
        ...state,
        draftTarget: action.value,
      };

    case "evidence_recorded":
      return {
        ...state,
        evidence: retainEvidence(state.evidence, action.record),
      };
  }
};

const mapCodeToPhase = (code: string): ConnectionPhase => {
  switch (code) {
    case "invalid_target":
      return "invalid_target";
    case "console_backend_unreachable":
      return "console_backend_unreachable";
    case "upstream_unreachable":
    case "rpc_remote_error":
    case "rpc_protocol_error":
      return "unreachable";
    case "malformed_response":
      return "malformed_response";
    case "upstream_timeout":
    case "rpc_decode_error":
    case "response_too_large":
      return "rpc_error";
    default:
      return "rpc_error";
  }
};

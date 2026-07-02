import type { ConnectionSuccess } from "../connection/contracts.js";

export type ConnectionPhase =
  | "not_configured"
  | "connecting"
  | "connected"
  | "invalid_target"
  | "unreachable"
  | "rpc_error"
  | "malformed_response";

export type EvidenceRecord = {
  readonly id: string;
  readonly operation: string;
  readonly label: string;
  readonly equivalentCli: string;
  readonly request: unknown;
  readonly response: unknown;
  readonly durationMs: number;
};

export type SourceRecord = {
  readonly id: string;
  readonly kind: string;
  readonly enabled: boolean;
  readonly description: string | null;
  readonly toolCount: number;
  readonly nodeSpecCount: number;
  readonly reducerCount: number;
  readonly promptCount: number;
  readonly resourceCount: number;
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
  readonly sources: ReadonlyArray<SourceRecord>;
  readonly sourcesLoading: boolean;
  readonly sourceError: string | null;
};

export const STORAGE_KEY = "lda.workflowConsole.target";

const safeLocalStorage = (): Storage | null => {
  try {
    return typeof localStorage !== "undefined" ? localStorage : null;
  } catch {
    return null;
  }
};

const safeSessionStorage = (): Storage | null => {
  try {
    return typeof sessionStorage !== "undefined" ? sessionStorage : null;
  } catch {
    return null;
  }
};

const getDefaultTarget = (): string => {
  const ls = safeLocalStorage();
  return ls?.getItem(STORAGE_KEY) ?? "http://127.0.0.1:8765/rpc";
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
  sources: [],
  sourcesLoading: false,
  sourceError: null,
});

export type ConnectionAction =
  | { readonly type: "submit"; readonly target: string }
  | { readonly type: "success"; readonly data: ConnectionSuccess }
  | { readonly type: "failure"; readonly code: string; readonly message: string }
  | { readonly type: "draft_changed"; readonly value: string }
  | { readonly type: "sources_loading" }
  | {
      readonly type: "sources_loaded";
      readonly sources: ReadonlyArray<SourceRecord>;
      readonly evidence: EvidenceRecord;
    }
  | {
      readonly type: "sources_error";
      readonly message: string;
      readonly evidence?: EvidenceRecord;
    }
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
        sources: [],
        sourceError: null,
        sourcesLoading: false,
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
        sourcesLoading: true,
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

    case "sources_loading":
      return {
        ...state,
        sourcesLoading: true,
        sourceError: null,
      };

    case "sources_loaded":
      return {
        ...state,
        sources: action.sources,
        sourcesLoading: false,
        sourceError: null,
        evidence: appendEvidence(state.evidence, action.evidence),
      };

    case "sources_error":
      return {
        ...state,
        sourcesLoading: false,
        sourceError: action.message,
        evidence: action.evidence
          ? appendEvidence(state.evidence, action.evidence)
          : state.evidence,
      };

    case "evidence_recorded":
      return {
        ...state,
        evidence: appendEvidence(state.evidence, action.record),
      };
  }
};

const appendEvidence = (
  existing: ReadonlyArray<EvidenceRecord>,
  record: EvidenceRecord,
): ReadonlyArray<EvidenceRecord> => [...existing, record];

const mapCodeToPhase = (code: string): ConnectionPhase => {
  switch (code) {
    case "invalid_target":
      return "invalid_target";
    case "upstream_unreachable":
    case "rpc_remote_error":
    case "rpc_protocol_error":
      return "unreachable";
    case "upstream_timeout":
    case "rpc_decode_error":
    case "response_too_large":
      return "rpc_error";
    default:
      return "rpc_error";
  }
};

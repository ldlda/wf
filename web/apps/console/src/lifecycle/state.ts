import type {
  ArtifactList,
  ArtifactDetail,
  DeploymentList,
  DeploymentDetail,
  DeploymentValidation,
  RunList,
  RunDetail,
  TracePage,
} from "./models.js";

export type LoadState<T> =
  | { readonly phase: "idle" }
  | { readonly phase: "loading"; readonly previous: T | null }
  | { readonly phase: "loaded"; readonly value: T }
  | { readonly phase: "error"; readonly message: string; readonly previous: T | null };

export type EvidenceRecord = {
  readonly id: string;
  readonly operation: string;
  readonly label: string;
  readonly equivalentCli: string;
  readonly request: unknown;
  readonly response: unknown;
  readonly durationMs: number;
};

export type LifecycleError = {
  readonly operation: string;
  readonly message: string;
  readonly timestamp: number;
};

export type LifecycleState = {
  readonly artifactList: LoadState<ArtifactList>;
  readonly deploymentList: LoadState<DeploymentList>;
  readonly runList: LoadState<RunList>;
  readonly selectedArtifactId: string | null;
  readonly artifactDetail: ArtifactDetail | null;
  readonly selectedDeploymentId: string | null;
  readonly deploymentDetail: DeploymentDetail | null;
  readonly deploymentValidation: DeploymentValidation | null;
  readonly selectedRunId: string | null;
  readonly runDetail: RunDetail | null;
  readonly trace: TracePage | null;
  readonly rawEvidence: ReadonlyArray<EvidenceRecord>;
  readonly errors: ReadonlyArray<LifecycleError>;
};

export const initialLifecycleState: LifecycleState = {
  artifactList: { phase: "idle" },
  deploymentList: { phase: "idle" },
  runList: { phase: "idle" },
  selectedArtifactId: null,
  artifactDetail: null,
  selectedDeploymentId: null,
  deploymentDetail: null,
  deploymentValidation: null,
  selectedRunId: null,
  runDetail: null,
  trace: null,
  rawEvidence: [],
  errors: [],
};

export type LifecycleAction =
  | { readonly type: "targetChanged" }
  | { readonly type: "selectArtifact"; readonly artifactId: string | null }
  | { readonly type: "selectDeployment"; readonly deploymentId: string | null }
  | { readonly type: "selectRun"; readonly runId: string | null }
  | { readonly type: "setArtifactListPhase"; readonly phase: "idle" | "loading" | "error"; readonly message?: string }
  | { readonly type: "setArtifactListPhase"; readonly phase: "loaded"; readonly value: ArtifactList }
  | { readonly type: "setDeploymentListPhase"; readonly phase: "idle" | "loading" | "error"; readonly message?: string }
  | { readonly type: "setDeploymentListPhase"; readonly phase: "loaded"; readonly value: DeploymentList }
  | { readonly type: "setRunListPhase"; readonly phase: "idle" | "loading" | "error"; readonly message?: string }
  | { readonly type: "setRunListPhase"; readonly phase: "loaded"; readonly value: RunList }
  | { readonly type: "appendArtifactList"; readonly value: ArtifactList }
  | { readonly type: "appendRunList"; readonly value: RunList }
  | { readonly type: "setArtifactDetail"; readonly detail: ArtifactDetail | null }
  | { readonly type: "setDeploymentDetail"; readonly detail: DeploymentDetail | null }
  | { readonly type: "setDeploymentValidation"; readonly validation: DeploymentValidation | null }
  | { readonly type: "setRunDetail"; readonly detail: RunDetail | null }
  | { readonly type: "setTrace"; readonly trace: TracePage | null }
  | { readonly type: "setRawEvidence"; readonly evidence: ReadonlyArray<EvidenceRecord> }
  | { readonly type: "pushError"; readonly error: LifecycleError };

const setLoadPhase = <T>(
  current: LoadState<T>,
  action: { phase: string; value?: T; message?: string },
): LoadState<T> => {
  switch (action.phase) {
    case "idle":
      return { phase: "idle" };
    case "loading":
      return { phase: "loading", previous: current.phase === "loaded" ? current.value : current.phase === "error" ? current.previous : null };
    case "loaded":
      return { phase: "loaded", value: action.value as T };
    case "error":
      return {
        phase: "error",
        message: action.message ?? "unknown error",
        previous: current.phase === "loaded" ? current.value : current.phase === "error" ? current.previous : null,
      };
    default:
      return current;
  }
};

export const lifecycleReducer = (
  state: LifecycleState,
  action: LifecycleAction,
): LifecycleState => {
  switch (action.type) {
    case "targetChanged":
      return initialLifecycleState;

    case "selectArtifact":
      return {
        ...state,
        selectedArtifactId: action.artifactId,
        selectedDeploymentId: null,
        selectedRunId: null,
        artifactDetail: null,
        deploymentDetail: null,
        deploymentValidation: null,
        runDetail: null,
        trace: null,
      };

    case "selectDeployment":
      return {
        ...state,
        selectedDeploymentId: action.deploymentId,
        selectedRunId: null,
        deploymentDetail: null,
        deploymentValidation: null,
        runDetail: null,
        trace: null,
      };

    case "selectRun":
      return {
        ...state,
        selectedRunId: action.runId,
        runDetail: null,
        trace: null,
      };

    case "setArtifactListPhase":
      return {
        ...state,
        artifactList: setLoadPhase(state.artifactList, action),
      };

    case "setDeploymentListPhase":
      return {
        ...state,
        deploymentList: setLoadPhase(state.deploymentList, action),
      };

    case "setRunListPhase":
      return {
        ...state,
        runList: setLoadPhase(state.runList, action),
      };

    case "appendArtifactList": {
      const previous = state.artifactList.phase === "loaded" ? state.artifactList.value : null;
      return {
        ...state,
        artifactList: {
          phase: "loaded",
          value: {
            items: [...(previous?.items ?? []), ...action.value.items],
            nextCursor: action.value.nextCursor,
            total: action.value.total,
          },
        },
      };
    }

    case "appendRunList": {
      const previous = state.runList.phase === "loaded" ? state.runList.value : null;
      return {
        ...state,
        runList: {
          phase: "loaded",
          value: {
            items: [...(previous?.items ?? []), ...action.value.items],
            nextCursor: action.value.nextCursor,
            total: action.value.total,
          },
        },
      };
    }

    case "setArtifactDetail":
      return {
        ...state,
        artifactDetail: action.detail,
      };

    case "setDeploymentDetail":
      return {
        ...state,
        deploymentDetail: action.detail,
      };

    case "setDeploymentValidation":
      return {
        ...state,
        deploymentValidation: action.validation,
      };

    case "setRunDetail":
      return {
        ...state,
        runDetail: action.detail,
      };

    case "setTrace":
      return {
        ...state,
        trace: action.trace,
      };

    case "setRawEvidence":
      return {
        ...state,
        rawEvidence: action.evidence,
      };

    case "pushError":
      return {
        ...state,
        errors: [...state.errors, action.error],
      };

    default:
      return state;
  }
};

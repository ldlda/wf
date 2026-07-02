import { useReducer, useEffect, useRef, useCallback } from "react";
import { callOperation } from "../connection/api.js";
import type { OperationName } from "../connection/contracts.js";
import {
  decodeArtifactList,
  decodeArtifactDetail,
  decodeDeploymentList,
  decodeDeploymentDetail,
  decodeDeploymentValidation,
  decodeRunList,
  decodeRunDetail,
  decodeTracePage,
} from "./models.js";
import { lifecycleReducer, initialLifecycleState, type LifecycleState, type EvidenceRecord } from "./state.js";

export type LifecycleExplorerController = {
  readonly state: LifecycleState;
  readonly selectArtifact: (artifactId: string | null) => void;
  readonly selectDeployment: (deploymentId: string | null) => void;
  readonly selectRun: (runId: string | null) => void;
  readonly refresh: () => void;
  readonly loadMoreArtifacts: () => void;
  readonly loadMoreRuns: () => void;
  readonly loadTrace: (start: number, limit: number) => void;
};

export const useLifecycleExplorer = (
  target: string | null,
  recordEvidence: (record: {
    id: string;
    operation: string;
    label: string;
    equivalentCli: string;
    request: unknown;
    response: unknown;
    durationMs: number;
  }) => void,
): LifecycleExplorerController => {
  const [state, dispatch] = useReducer(lifecycleReducer, initialLifecycleState);
  const generationRef = useRef(0);
  const inspectGenerationRef = useRef(0);
  const rawEvidenceRef = useRef<ReadonlyArray<EvidenceRecord>>([]);
  const evidenceSeqRef = useRef(0);

  const executeOperation = useCallback(
    async (
      operation: OperationName,
      params: unknown,
      generation: number,
      checkGenerationRef: React.MutableRefObject<number>,
      onSuccess: (interpreted: unknown) => void,
    ) => {
      if (!target) return;
      try {
        const result = await callOperation(operation, target, params);
        if (generation !== checkGenerationRef.current) return;
        if (result.ok) {
          const seq = evidenceSeqRef.current++;
          const record: EvidenceRecord = {
            id: `${result.operation}-${seq}`,
            operation: result.operation,
            label: result.operation,
            equivalentCli: result.equivalentCli,
            request: result.exchange.request,
            response: result.exchange.response,
            durationMs: result.durationMs,
          };
          recordEvidence(record);
          rawEvidenceRef.current = [...rawEvidenceRef.current, record];
          dispatch({ type: "setRawEvidence", evidence: rawEvidenceRef.current });
          try {
            onSuccess(result.interpreted);
          } catch (decodeError) {
            dispatch({
              type: "pushError",
              error: {
                operation: result.operation,
                message: decodeError instanceof Error ? decodeError.message : String(decodeError),
                timestamp: Date.now(),
              },
            });
          }
        } else {
          dispatch({
            type: "pushError",
            error: {
              operation,
              message: result.error.message,
              timestamp: Date.now(),
            },
          });
        }
      } catch (rpcError) {
        dispatch({
          type: "pushError",
          error: {
            operation,
            message: rpcError instanceof Error ? rpcError.message : String(rpcError),
            timestamp: Date.now(),
          },
        });
      }
    },
    [target, recordEvidence],
  );

  useEffect(() => {
    if (!target) return;
    generationRef.current++;
    const generation = generationRef.current;
    rawEvidenceRef.current = [];
    dispatch({ type: "targetChanged" });

    executeOperation("workflow.artifacts.list", { limit: 50 }, generation, generationRef, (interpreted) => {
      dispatch({ type: "setArtifactListPhase", phase: "loaded", value: decodeArtifactList(interpreted) });
    });

    executeOperation("workflow.deployments.list", {}, generation, generationRef, (interpreted) => {
      dispatch({ type: "setDeploymentListPhase", phase: "loaded", value: decodeDeploymentList(interpreted) });
    });

    executeOperation("workflow.runs.list", { limit: 50 }, generation, generationRef, (interpreted) => {
      dispatch({ type: "setRunListPhase", phase: "loaded", value: decodeRunList(interpreted) });
    });
  }, [target, executeOperation]);

  const selectArtifact = useCallback(
    (artifactId: string | null) => {
      dispatch({ type: "selectArtifact", artifactId });
      if (!artifactId || !target) return;
      inspectGenerationRef.current++;
      const generation = inspectGenerationRef.current;
      const [id, version] = artifactId.split("@");
      executeOperation(
        "workflow.artifacts.inspect",
        { artifact_id: id, version: Number(version) },
        generation,
        inspectGenerationRef,
        (interpreted) => {
          dispatch({ type: "setArtifactDetail", detail: decodeArtifactDetail(interpreted) });
        },
      );
    },
    [target, executeOperation],
  );

  const selectDeployment = useCallback(
    (deploymentId: string | null) => {
      dispatch({ type: "selectDeployment", deploymentId });
      if (!deploymentId || !target) return;
      inspectGenerationRef.current++;
      const generation = inspectGenerationRef.current;
      // Deployment selection fans out to inspect + validate. Both describe the
      // same selected deployment, so they must share one generation token.
      executeOperation(
        "workflow.deployments.inspect",
        { deployment_id: deploymentId },
        generation,
        inspectGenerationRef,
        (interpreted) => {
          dispatch({ type: "setDeploymentDetail", detail: decodeDeploymentDetail(interpreted) });
        },
      );
      executeOperation(
        "workflow.deployments.validate",
        { deployment_id: deploymentId },
        generation,
        inspectGenerationRef,
        (interpreted) => {
          dispatch({ type: "setDeploymentValidation", validation: decodeDeploymentValidation(interpreted) });
        },
      );
    },
    [target, executeOperation],
  );

  const selectRun = useCallback(
    (runId: string | null) => {
      dispatch({ type: "selectRun", runId });
      if (!runId || !target) return;
      inspectGenerationRef.current++;
      const generation = inspectGenerationRef.current;
      executeOperation(
        "workflow.runs.inspect",
        { run_id: runId },
        generation,
        inspectGenerationRef,
        (interpreted) => {
          dispatch({ type: "setRunDetail", detail: decodeRunDetail(interpreted) });
        },
      );
    },
    [target, executeOperation],
  );

  const refresh = useCallback(() => {
    if (!target) return;
    generationRef.current++;
    const generation = generationRef.current;
    executeOperation("workflow.artifacts.list", { limit: 50 }, generation, generationRef, (interpreted) => {
      dispatch({ type: "setArtifactListPhase", phase: "loaded", value: decodeArtifactList(interpreted) });
    });
    executeOperation("workflow.deployments.list", {}, generation, generationRef, (interpreted) => {
      dispatch({ type: "setDeploymentListPhase", phase: "loaded", value: decodeDeploymentList(interpreted) });
    });
    executeOperation("workflow.runs.list", { limit: 50 }, generation, generationRef, (interpreted) => {
      dispatch({ type: "setRunListPhase", phase: "loaded", value: decodeRunList(interpreted) });
    });
  }, [target, executeOperation]);

  const loadMoreArtifacts = useCallback(() => {
    const current = state.artifactList;
    if (current.phase !== "loaded" || !current.value.nextCursor || !target) return;
    generationRef.current++;
    const generation = generationRef.current;
    executeOperation(
      "workflow.artifacts.list",
      { cursor: current.value.nextCursor, limit: 50 },
      generation,
      generationRef,
      (interpreted) => {
        dispatch({ type: "appendArtifactList", value: decodeArtifactList(interpreted) });
      },
    );
  }, [state.artifactList, target, executeOperation]);

  const loadMoreRuns = useCallback(() => {
    const current = state.runList;
    if (current.phase !== "loaded" || !current.value.nextCursor || !target) return;
    generationRef.current++;
    const generation = generationRef.current;
    executeOperation(
      "workflow.runs.list",
      { cursor: current.value.nextCursor, limit: 50 },
      generation,
      generationRef,
      (interpreted) => {
        dispatch({ type: "appendRunList", value: decodeRunList(interpreted) });
      },
    );
  }, [state.runList, target, executeOperation]);

  const loadTrace = useCallback(
    (start: number, limit: number) => {
      if (!state.selectedRunId || !target) return;
      inspectGenerationRef.current++;
      const generation = inspectGenerationRef.current;
      executeOperation(
        "workflow.runs.trace",
        { run_id: state.selectedRunId, trace_range: { start, limit } },
        generation,
        inspectGenerationRef,
        (interpreted) => {
          dispatch({ type: "setTrace", trace: decodeTracePage(interpreted) });
        },
      );
    },
    [state.selectedRunId, target, executeOperation],
  );

  return {
    state,
    selectArtifact,
    selectDeployment,
    selectRun,
    refresh,
    loadMoreArtifacts,
    loadMoreRuns,
    loadTrace,
  };
};

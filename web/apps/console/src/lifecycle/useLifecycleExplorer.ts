import { useCallback, useEffect, useReducer, useRef, type MutableRefObject } from "react";
import { ConsoleClientError } from "../workspace/domain/errors.js";
import type { LifecycleClients } from "../workspace/domain/lifecycle-clients.js";
import { lifecycleReducer, initialLifecycleState, type LifecycleState } from "./state.js";

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

type ReadFailure = (message: string, operation: string) => void;

const readErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const readErrorOperation = (error: unknown): string =>
  error instanceof ConsoleClientError ? error.operation : "lifecycle";

export const useLifecycleExplorer = (
  clients: LifecycleClients | null,
): LifecycleExplorerController => {
  const [state, dispatch] = useReducer(lifecycleReducer, initialLifecycleState);
  const generationRef = useRef(0);
  const artifactListGenerationRef = useRef(0);
  const artifactDetailGenerationRef = useRef(0);
  const deploymentListGenerationRef = useRef(0);
  const deploymentDetailGenerationRef = useRef(0);
  const runListGenerationRef = useRef(0);
  const runDetailGenerationRef = useRef(0);
  const committedClientsRef = useRef<LifecycleClients | null | undefined>(undefined);

  const invalidateDetailReads = useCallback((): void => {
    artifactDetailGenerationRef.current++;
    deploymentDetailGenerationRef.current++;
    runDetailGenerationRef.current++;
  }, []);

  const executeRead = useCallback(
    async <T>(
      read: () => Promise<T>,
      generation: number,
      checkGenerationRef: MutableRefObject<number>,
      targetGeneration: number,
      onSuccess: (value: T) => void,
      onFailure?: ReadFailure,
    ): Promise<void> => {
      try {
        const value = await read();
        if (
          targetGeneration !== generationRef.current ||
          generation !== checkGenerationRef.current
        ) return;
        onSuccess(value);
      } catch (error) {
        if (
          targetGeneration !== generationRef.current ||
          generation !== checkGenerationRef.current
        ) return;
        const message = readErrorMessage(error);
        const operation = readErrorOperation(error);
        onFailure?.(message, operation);
        dispatch({
          type: "pushError",
          error: {
            operation,
            message,
            timestamp: Date.now(),
          },
        });
      }
    },
    [],
  );

  const startCollectionReads = useCallback(
    (
      artifactGeneration: number,
      deploymentGeneration: number,
      runGeneration: number,
      targetGeneration: number,
    ): void => {
      if (!clients) return;
      dispatch({ type: "setArtifactListPhase", phase: "loading" });
      dispatch({ type: "setDeploymentListPhase", phase: "loading" });
      dispatch({ type: "setRunListPhase", phase: "loading" });

      void executeRead(
        () => clients.artifacts.list({ limit: 50 }),
        artifactGeneration,
        artifactListGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setArtifactListPhase", phase: "loaded", value }),
        (message) => dispatch({ type: "setArtifactListPhase", phase: "error", message }),
      );
      void executeRead(
        () => clients.deployments.list(),
        deploymentGeneration,
        deploymentListGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setDeploymentListPhase", phase: "loaded", value }),
        (message) => dispatch({ type: "setDeploymentListPhase", phase: "error", message }),
      );
      void executeRead(
        () => clients.runs.list({ limit: 50 }),
        runGeneration,
        runListGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setRunListPhase", phase: "loaded", value }),
        (message) => dispatch({ type: "setRunListPhase", phase: "error", message }),
      );
    },
    [clients, executeRead],
  );

  useEffect(() => {
    const targetGeneration = ++generationRef.current;
    committedClientsRef.current = clients;
    const artifactGeneration = ++artifactListGenerationRef.current;
    const deploymentGeneration = ++deploymentListGenerationRef.current;
    const runGeneration = ++runListGenerationRef.current;
    invalidateDetailReads();
    dispatch({ type: "targetChanged" });
    startCollectionReads(
      artifactGeneration,
      deploymentGeneration,
      runGeneration,
      targetGeneration,
    );
  }, [clients, invalidateDetailReads, startCollectionReads]);

  const selectArtifact = useCallback(
    (artifactKey: string | null): void => {
      invalidateDetailReads();
      dispatch({ type: "selectArtifact", artifactId: artifactKey });
      if (!artifactKey || !clients) return;
      const generation = artifactDetailGenerationRef.current;
      const separator = artifactKey.lastIndexOf("@");
      const artifactId = artifactKey.slice(0, separator);
      const version = Number(artifactKey.slice(separator + 1));
      void executeRead(
        () => clients.artifacts.inspect(artifactId, version),
        generation,
        artifactDetailGenerationRef,
        generationRef.current,
        (value) => dispatch({ type: "setArtifactDetail", detail: value }),
      );
    },
    [clients, executeRead, invalidateDetailReads],
  );

  const selectDeployment = useCallback(
    (deploymentId: string | null): void => {
      invalidateDetailReads();
      dispatch({ type: "selectDeployment", deploymentId });
      if (!deploymentId || !clients) return;
      const generation = deploymentDetailGenerationRef.current;
      const targetGeneration = generationRef.current;
      // Inspection and validation describe one URL-owned deployment selection.
      void executeRead(
        () => clients.deployments.inspect(deploymentId),
        generation,
        deploymentDetailGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setDeploymentDetail", detail: value }),
      );
      void executeRead(
        () => clients.deployments.validate(deploymentId),
        generation,
        deploymentDetailGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setDeploymentValidation", validation: value }),
      );
    },
    [clients, executeRead, invalidateDetailReads],
  );

  const selectRun = useCallback(
    (runId: string | null): void => {
      invalidateDetailReads();
      dispatch({ type: "selectRun", runId });
      if (!runId || !clients) return;
      const generation = runDetailGenerationRef.current;
      const targetGeneration = generationRef.current;
      void executeRead(
        () => clients.runs.inspect(runId),
        generation,
        runDetailGenerationRef,
        targetGeneration,
        (value) => {
          dispatch({ type: "setRunDetail", detail: value });
          if (value.traceCount > 0) {
            void executeRead(
              () => clients.runs.trace(runId, 0, 50),
              generation,
              runDetailGenerationRef,
              targetGeneration,
              (trace) => dispatch({ type: "setTrace", trace }),
            );
          }
        },
      );
    },
    [clients, executeRead, invalidateDetailReads],
  );

  const refresh = useCallback((): void => {
    if (!clients) return;
    generationRef.current++;
    invalidateDetailReads();
    artifactListGenerationRef.current++;
    deploymentListGenerationRef.current++;
    runListGenerationRef.current++;
    startCollectionReads(
      artifactListGenerationRef.current,
      deploymentListGenerationRef.current,
      runListGenerationRef.current,
      generationRef.current,
    );
  }, [clients, invalidateDetailReads, startCollectionReads]);

  const loadMoreArtifacts = useCallback((): void => {
    const current = state.artifactList;
    if (current.phase !== "loaded" || !current.value.nextCursor || !clients) return;
    const cursor = current.value.nextCursor;
    const generation = ++artifactListGenerationRef.current;
    void executeRead(
      () => clients.artifacts.list({ cursor, limit: 50 }),
      generation,
      artifactListGenerationRef,
      generationRef.current,
      (value) => dispatch({ type: "appendArtifactList", value }),
    );
  }, [clients, executeRead, state.artifactList]);

  const loadMoreRuns = useCallback((): void => {
    const current = state.runList;
    if (current.phase !== "loaded" || !current.value.nextCursor || !clients) return;
    const cursor = current.value.nextCursor;
    const generation = ++runListGenerationRef.current;
    void executeRead(
      () => clients.runs.list({ cursor, limit: 50 }),
      generation,
      runListGenerationRef,
      generationRef.current,
      (value) => dispatch({ type: "appendRunList", value }),
    );
  }, [clients, executeRead, state.runList]);

  const loadTrace = useCallback(
    (start: number, limit: number): void => {
      if (!state.selectedRunId || !clients) return;
      const generation = ++runDetailGenerationRef.current;
      const targetGeneration = generationRef.current;
      const runId = state.selectedRunId;
      void executeRead(
        () => clients.runs.trace(runId, start, limit),
        generation,
        runDetailGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setTrace", trace: value }),
      );
    },
    [clients, executeRead, state.selectedRunId],
  );

  return {
    // A client change is visible before passive effects run. Project the old
    // reducer snapshot to an empty state until the new target is committed.
    state:
      committedClientsRef.current === clients
        ? state
        : initialLifecycleState,
    selectArtifact,
    selectDeployment,
    selectRun,
    refresh,
    loadMoreArtifacts,
    loadMoreRuns,
    loadTrace,
  };
};

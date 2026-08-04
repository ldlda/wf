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
  const artifactGenerationRef = useRef(0);
  const deploymentGenerationRef = useRef(0);
  const runGenerationRef = useRef(0);

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
        artifactGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setArtifactListPhase", phase: "loaded", value }),
        (message) => dispatch({ type: "setArtifactListPhase", phase: "error", message }),
      );
      void executeRead(
        () => clients.deployments.list(),
        deploymentGeneration,
        deploymentGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setDeploymentListPhase", phase: "loaded", value }),
        (message) => dispatch({ type: "setDeploymentListPhase", phase: "error", message }),
      );
      void executeRead(
        () => clients.runs.list({ limit: 50 }),
        runGeneration,
        runGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setRunListPhase", phase: "loaded", value }),
        (message) => dispatch({ type: "setRunListPhase", phase: "error", message }),
      );
    },
    [clients, executeRead],
  );

  useEffect(() => {
    const targetGeneration = ++generationRef.current;
    const artifactGeneration = ++artifactGenerationRef.current;
    const deploymentGeneration = ++deploymentGenerationRef.current;
    const runGeneration = ++runGenerationRef.current;
    dispatch({ type: "targetChanged" });
    startCollectionReads(
      artifactGeneration,
      deploymentGeneration,
      runGeneration,
      targetGeneration,
    );
  }, [startCollectionReads]);

  const selectArtifact = useCallback(
    (artifactKey: string | null): void => {
      dispatch({ type: "selectArtifact", artifactId: artifactKey });
      if (!artifactKey || !clients) return;
      artifactGenerationRef.current++;
      const generation = artifactGenerationRef.current;
      const separator = artifactKey.lastIndexOf("@");
      const artifactId = artifactKey.slice(0, separator);
      const version = Number(artifactKey.slice(separator + 1));
      void executeRead(
        () => clients.artifacts.inspect(artifactId, version),
        generation,
        artifactGenerationRef,
        generationRef.current,
        (value) => dispatch({ type: "setArtifactDetail", detail: value }),
      );
    },
    [clients, executeRead],
  );

  const selectDeployment = useCallback(
    (deploymentId: string | null): void => {
      dispatch({ type: "selectDeployment", deploymentId });
      if (!deploymentId || !clients) return;
      deploymentGenerationRef.current++;
      const generation = deploymentGenerationRef.current;
      const targetGeneration = generationRef.current;
      // Inspection and validation describe one URL-owned deployment selection.
      void executeRead(
        () => clients.deployments.inspect(deploymentId),
        generation,
        deploymentGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setDeploymentDetail", detail: value }),
      );
      void executeRead(
        () => clients.deployments.validate(deploymentId),
        generation,
        deploymentGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setDeploymentValidation", validation: value }),
      );
    },
    [clients, executeRead],
  );

  const selectRun = useCallback(
    (runId: string | null): void => {
      dispatch({ type: "selectRun", runId });
      if (!runId || !clients) return;
      runGenerationRef.current++;
      const generation = runGenerationRef.current;
      const targetGeneration = generationRef.current;
      void executeRead(
        () => clients.runs.inspect(runId),
        generation,
        runGenerationRef,
        targetGeneration,
        (value) => {
          dispatch({ type: "setRunDetail", detail: value });
          if (value.traceCount > 0) {
            void executeRead(
              () => clients.runs.trace(runId, 0, 50),
              generation,
              runGenerationRef,
              targetGeneration,
              (trace) => dispatch({ type: "setTrace", trace }),
            );
          }
        },
      );
    },
    [clients, executeRead],
  );

  const refresh = useCallback((): void => {
    if (!clients) return;
    generationRef.current++;
    artifactGenerationRef.current++;
    deploymentGenerationRef.current++;
    runGenerationRef.current++;
    startCollectionReads(
      artifactGenerationRef.current,
      deploymentGenerationRef.current,
      runGenerationRef.current,
      generationRef.current,
    );
  }, [clients, startCollectionReads]);

  const loadMoreArtifacts = useCallback((): void => {
    const current = state.artifactList;
    if (current.phase !== "loaded" || !current.value.nextCursor || !clients) return;
    const cursor = current.value.nextCursor;
    artifactGenerationRef.current++;
    const generation = artifactGenerationRef.current;
    void executeRead(
      () => clients.artifacts.list({ cursor, limit: 50 }),
      generation,
      artifactGenerationRef,
      generationRef.current,
      (value) => dispatch({ type: "appendArtifactList", value }),
    );
  }, [clients, executeRead, state.artifactList]);

  const loadMoreRuns = useCallback((): void => {
    const current = state.runList;
    if (current.phase !== "loaded" || !current.value.nextCursor || !clients) return;
    const cursor = current.value.nextCursor;
    runGenerationRef.current++;
    const generation = runGenerationRef.current;
    void executeRead(
      () => clients.runs.list({ cursor, limit: 50 }),
      generation,
      runGenerationRef,
      generationRef.current,
      (value) => dispatch({ type: "appendRunList", value }),
    );
  }, [clients, executeRead, state.runList]);

  const loadTrace = useCallback(
    (start: number, limit: number): void => {
      if (!state.selectedRunId || !clients) return;
      runGenerationRef.current++;
      const generation = runGenerationRef.current;
      const targetGeneration = generationRef.current;
      const runId = state.selectedRunId;
      void executeRead(
        () => clients.runs.trace(runId, start, limit),
        generation,
        runGenerationRef,
        targetGeneration,
        (value) => dispatch({ type: "setTrace", trace: value }),
      );
    },
    [clients, executeRead, state.selectedRunId],
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

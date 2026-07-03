import { useState, useMemo } from "react";
import type { LifecycleExplorerController } from "./useLifecycleExplorer.js";
import { RecordColumns } from "./RecordColumns.js";
import { RecordDetails } from "./RecordDetails.js";
import { buildWorkflowGraph } from "../graph/graph-model.js";
import { WorkflowGraph } from "../graph/WorkflowGraph.js";
import { buildTraceFrames } from "../execution/trace-model.js";
import { ExecutionView } from "../execution/ExecutionView.js";
import type { LoadState } from "./state.js";

type LifecycleExplorerProps = {
  readonly controller: LifecycleExplorerController;
};

type FocusMode = "lifecycle" | "graph" | "execution" | "raw";

const loadedItems = <T,>(
  state: LoadState<{ readonly items: ReadonlyArray<T> }>,
): ReadonlyArray<T> =>
  state.phase === "loaded" ? state.value.items : state.phase === "loading" || state.phase === "error" ? state.previous?.items ?? [] : [];

const listStatus = <T,>(label: string, state: LoadState<T>) => {
  if (state.phase === "loading") return <p role="status">Loading {label}...</p>;
  if (state.phase === "error") return <p role="alert">Could not load {label}: {state.message}</p>;
  return null;
};

export const LifecycleExplorer = ({ controller }: LifecycleExplorerProps) => {
  const { state } = controller;
  const [focusMode, setFocusMode] = useState<FocusMode>("lifecycle");

  const artifacts = loadedItems(state.artifactList);
  const deployments = loadedItems(state.deploymentList);
  const runs = loadedItems(state.runList);

  const graphModel = useMemo(() => {
    if (!state.artifactDetail?.plan) return null;
    const plan = state.artifactDetail.plan as {
      nodes: ReadonlyArray<Record<string, unknown>>;
      edges: ReadonlyArray<Record<string, unknown>>;
    };
    if (!plan.nodes || !plan.edges) return null;
    return buildWorkflowGraph(plan);
  }, [state.artifactDetail?.plan]);

  const traceResult = useMemo(() => {
    if (!state.trace) return null;
    return buildTraceFrames(state.trace);
  }, [state.trace]);

  return (
    <div className="lifecycle-explorer">
      <nav className="focus-nav" aria-label="Focus modes">
        <button
          onClick={() => setFocusMode("lifecycle")}
          className={focusMode === "lifecycle" ? "active" : ""}
        >
          Lifecycle
        </button>
        <button
          onClick={() => setFocusMode("graph")}
          disabled={!graphModel}
          className={focusMode === "graph" ? "active" : ""}
        >
          Graph
        </button>
        <button
          onClick={() => setFocusMode("execution")}
          disabled={!traceResult}
          className={focusMode === "execution" ? "active" : ""}
        >
          Execution
        </button>
        <button
          onClick={() => setFocusMode("raw")}
          className={focusMode === "raw" ? "active" : ""}
        >
          Raw
        </button>
      </nav>

      {focusMode === "lifecycle" && (
        <div className="lifecycle-content">
          <div className="lifecycle-status">
            {listStatus("artifacts", state.artifactList)}
            {listStatus("deployments", state.deploymentList)}
            {listStatus("runs", state.runList)}
            {state.errors.map((error) => (
              <p role="alert" key={`${error.operation}-${error.timestamp}`}>
                {error.operation}: {error.message}
              </p>
            ))}
          </div>
          <RecordColumns
            artifacts={artifacts}
            deployments={deployments}
            runs={runs}
            selectedArtifactId={state.selectedArtifactId}
            selectedDeploymentId={state.selectedDeploymentId}
            selectedRunId={state.selectedRunId}
            onSelectArtifact={controller.selectArtifact}
            onSelectDeployment={controller.selectDeployment}
            onSelectRun={controller.selectRun}
            onLoadMoreArtifacts={controller.loadMoreArtifacts}
            hasMoreArtifacts={state.artifactList.phase === "loaded" && state.artifactList.value.nextCursor !== null}
            onLoadMoreRuns={controller.loadMoreRuns}
            hasMoreRuns={state.runList.phase === "loaded" && state.runList.value.nextCursor !== null}
          />
          <RecordDetails
            artifactDetail={state.artifactDetail}
            deploymentDetail={state.deploymentDetail}
            runDetail={state.runDetail}
          />
        </div>
      )}

      {focusMode === "graph" && graphModel && (
        <div className="graph-content">
          <WorkflowGraph model={graphModel} />
        </div>
      )}

      {focusMode === "execution" && traceResult && (
        <div className="execution-content">
          <ExecutionView
            frames={traceResult.frames}
            interrupt={state.runDetail?.interrupt ? {
              kind: state.runDetail.interrupt.kind,
              payload: state.runDetail.interrupt.payload,
              outcomes: state.runDetail.interrupt.outcomes,
              requestSchema: {},
              resumeSchema: {},
              typed: false,
            } : null}
          />
        </div>
      )}

      {focusMode === "raw" && (
        <div className="raw-content">
          <h3>Protocol Evidence</h3>
          {state.rawEvidence.length === 0 ? (
            <p className="empty-state">No evidence recorded yet.</p>
          ) : (
            <ul className="evidence-list">
              {state.rawEvidence.map((record) => (
                <li key={record.id}>
                  <span className="evidence-op">{record.operation}</span>
                  <span className="evidence-label">{record.label}</span>
                  <span className="evidence-duration">{record.durationMs}ms</span>
                  <details>
                    <summary>Equivalent CLI</summary>
                    <pre><code>{record.equivalentCli}</code></pre>
                  </details>
                  <details>
                    <summary>Request</summary>
                    <pre><code>{JSON.stringify(record.request, null, 2)}</code></pre>
                  </details>
                  <details>
                    <summary>Response</summary>
                    <pre><code>{JSON.stringify(record.response, null, 2)}</code></pre>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

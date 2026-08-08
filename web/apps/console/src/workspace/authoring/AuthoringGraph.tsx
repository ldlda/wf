import { useMemo } from "react";
import type { DraftWorkspace } from "../domain/draft-workspace-models.js";
import { WorkflowGraph } from "../../graph/WorkflowGraph.js";
import { projectAuthoringGraph, type WorkbenchSelection } from "./authoring-graph.js";

type AuthoringGraphProps = {
  readonly draft: DraftWorkspace["draft"];
  readonly selection: WorkbenchSelection;
  readonly onSelectionChange: (selection: WorkbenchSelection) => void;
};

export const AuthoringGraph = ({
  draft,
  selection,
  onSelectionChange,
}: AuthoringGraphProps) => {
  const model = useMemo(() => projectAuthoringGraph(draft), [draft]);
  const activeEdgeId =
    selection.kind === "edge"
      ? model.edges.find(
          (edge) => edge.source === selection.stepId && edge.label === selection.outcome,
        )?.id ?? null
      : null;
  const selectEdge = (edgeId: string): void => {
    const edge = model.edges.find((candidate) => candidate.id === edgeId);
    if (edge) {
      onSelectionChange({
        kind: "edge",
        stepId: edge.source,
        outcome: edge.label,
      });
    }
  };

  return (
    <section aria-label="Workflow graph" className="authoring-graph">
      <div className="authoring-graph__heading">
        <div>
          <p className="workspace-route-pending__eyebrow">Authoring canvas</p>
          <h2>Workflow graph</h2>
        </div>
        <span className="authoring-graph__selection" aria-live="polite">
          {selection.kind === "canvas" ? "Canvas" : selection.kind}
        </span>
      </div>
      <WorkflowGraph
        activeEdgeId={activeEdgeId}
        activeNodeId={selection.kind === "node" ? selection.nodeId : null}
        model={model}
        onCanvasSelect={() => onSelectionChange({ kind: "canvas" })}
        onEdgeSelect={selectEdge}
        onNodeSelect={(nodeId) => onSelectionChange({ kind: "node", nodeId })}
      />
      <div aria-label="Route outcomes" className="authoring-graph__routes">
        <h3>Route outcomes</h3>
        {model.edges.length > 0 ? (
          <ul>
            {model.edges.map((edge) => (
              <li key={edge.id}>
                <button
                  aria-pressed={activeEdgeId === edge.id}
                  className="authoring-graph__route"
                  data-edge-id={edge.id}
                  onClick={() => selectEdge(edge.id)}
                  type="button"
                >
                  <span>{edge.source}</span>
                  <strong>{edge.label || "unnamed"}</strong>
                  <span>{edge.target}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : <p>No routes in this draft.</p>}
      </div>
    </section>
  );
};

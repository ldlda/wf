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
  const routeEdges = model.edges.filter((edge) => edge.kind !== "contract");
  const activeNodeId =
    selection.kind === "node"
      ? selection.nodeId
      : selection.kind === "contract"
        ? `contract:${selection.contract}`
        : null;
  const activeEdgeId =
    selection.kind === "edge"
      ? routeEdges.find(
          (edge) => edge.source === selection.stepId && edge.label === selection.outcome,
        )?.id ?? null
      : null;
  const selectEdge = (edgeId: string): void => {
    const edge = routeEdges.find((candidate) => candidate.id === edgeId);
    if (edge) {
      onSelectionChange({
        kind: "edge",
        stepId: edge.source,
        outcome: edge.label,
      });
    }
  };
  const selectNode = (nodeId: string): void => {
    const node = model.nodes.find((candidate) => candidate.id === nodeId);
    if (node?.data.contract) {
      onSelectionChange({ kind: "contract", contract: node.data.contract });
      return;
    }
    onSelectionChange({ kind: "node", nodeId });
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
        activeNodeId={activeNodeId}
        model={model}
        onCanvasSelect={() => onSelectionChange({ kind: "canvas" })}
        onEdgeSelect={selectEdge}
        onNodeSelect={selectNode}
      />
      <div aria-label="Route outcomes" className="authoring-graph__routes">
        <h3>Route outcomes</h3>
        {routeEdges.length > 0 ? (
          <ul>
            {routeEdges.map((edge) => (
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
